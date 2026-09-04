#!/usr/bin/env python3
"""Thin Windows ModelDB driver for the msvc-wheel-dev wheel.

Not a port of nrn-modeldb-ci runmodels. No /bin/sh. Serial. Stdlib + PyYAML + neuron.

Unzip cache zips onto a C: workdir, honor yaml model_dir, nrnivmodl, write driver.hoc
with forward-slash verify_dir_, then nrniv -nobanner (cwd nrnmech.dll auto-load,
or -dll with forward slashes). Translate yaml script only for an allowlist. Windows-only skip
WINDOWS_SKIP (Lytton VERBATIM POSIX); do not yaml skip those ids.

--compile-launch-only stops after nrnivmodl + nrniv load (API completeness).
No .mod files: skip nrnivmodl and launch hoc-only (Linux runmodels does that).
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import traceback
import zipfile
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None


DRIVER_HOC_BODY = r"""
if (name_declared("verify_dir_") == 0) {
	execute("~strdef verify_dir_")
	execute("verify_dir_ = \".\"")
}
strdef verify_tstr_
objref verify_glist_, verify_xvec_, verify_yvec_, verify_file_
verify_file_ = new File()
sprint(verify_tstr_, "%s/gout", verify_dir_)
verify_file_.wopen(verify_tstr_)
verify_xvec_ = new Vector()
verify_yvec_ = new Vector()
verify_glist_ = new List("Graph")

proc verify_graph_() {local i, j, k
	verify_file_.printf("Graphs %d\n", verify_glist_.count)
	for i=0, verify_glist_.count-1 {
		verify_file_.printf("%s\n", verify_glist_.object(i))
		k = 0
		for (j=-1; (j=verify_glist_.object(i).line_info(j, verify_xvec_)) != -1; ){
			k += 1
		}
		verify_file_.printf("lines %d\n", k)
		for (j=-1; (j=verify_glist_.object(i).getline(j, verify_xvec_, verify_yvec_)) != -1; ){
			verify_file_.printf("points %d\n", verify_xvec_.size)
			verify_file_.printf("xvec%d\n", j)
			verify_xvec_.printf(verify_file_)
			verify_file_.printf("yvec%d\n", j)
			verify_yvec_.printf(verify_file_)
		}
	}
}
"""

DEFAULT_RUN = ["verify_graph_()"]


def posix(p: Path | str) -> str:
    return str(p).replace("\\", "/")


def is_junk_mod(path: Path) -> bool:
    name = path.name
    return name.startswith("._") or "__MACOSX" in path.parts


def _read_backup(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(str(path))
    text = path.read_text(encoding="utf-8", errors="replace")
    bak = path.with_name(path.name + ".bak")
    bak.write_text(text, encoding="utf-8")
    return text


def patch_51781_sed_seed(model_dir: Path) -> list[str]:
    """sed -i'.bak' -e 's#ropen(#// ropen(#g;s#rseed = fscan()#rseed=424242#g' testnet.hoc"""
    target = model_dir / "testnet.hoc"
    text = _read_backup(target)
    patched = text.replace("ropen(", "// ropen(").replace(
        "rseed = fscan()", "rseed=424242"
    )
    target.write_text(patched, encoding="utf-8")
    return [
        f"patched {target.name}: ropen( -> // ropen(; rseed = fscan() -> rseed=424242"
    ]


def patch_97756_startsw(model_dir: Path) -> list[str]:
    """sed -i'.bak' -e 's/^startsw()$/{startsw()}/g' ga_setup.hoc"""
    target = model_dir / "ga_setup.hoc"
    text = _read_backup(target)
    patched, n = re.subn(r"^startsw\(\)$", "{startsw()}", text, flags=re.M)
    target.write_text(patched, encoding="utf-8")
    return [f"patched {target.name}: startsw() -> {{startsw()}} ({n})"]


def patch_97917_mkdll(model_dir: Path) -> list[str]:
    """sed: s/mkdll_("nrntraub", "mod", s.s)) {/1) {\\n\\t\\tchdir("nrntraub")/g"""
    target = model_dir / "mosinit.hoc"
    text = _read_backup(target)
    old = 'mkdll_("nrntraub", "mod", s.s)) {'
    new = '1) {\n\t\tchdir("nrntraub")'
    n = text.count(old)
    target.write_text(text.replace(old, new), encoding="utf-8")
    return [f"patched {target.name}: skip mkdll_ nrntraub, chdir nrntraub ({n})"]


def patch_124291_ichan2(model_dir: Path) -> list[str]:
    """sed -i'.bak' -e 's/return 0;//g' */ichan2.mod (INITIAL + PROCEDURE)."""
    logs = []
    for target in sorted(model_dir.rglob("ichan2.mod")):
        if is_junk_mod(target):
            continue
        text = _read_backup(target)
        n = text.count("return 0;")
        target.write_text(text.replace("return 0;", ""), encoding="utf-8")
        logs.append(f"patched {target.relative_to(model_dir)}: stripped return 0; ({n})")
    if not logs:
        raise FileNotFoundError(f"no ichan2.mod under {model_dir}")
    return logs


def patch_266806_cao_constant(model_dir: Path) -> list[str]:
    """sed -i'.bak' -e '/^CONSTANT { cao = 2(mM) }$/d' Morphology_*/mod_files/cdp5StCmod.mod"""
    logs = []
    pat = re.compile(r"^CONSTANT \{ cao = 2\s*\(mM\) \}\s*\n?", re.M)
    for target in sorted(model_dir.rglob("cdp5StCmod.mod")):
        if is_junk_mod(target):
            continue
        text = _read_backup(target)
        patched, n = pat.subn("", text)
        n_asg = 0
        if not re.search(r"^\s*cao\s+\(mM\)\s*$", patched, re.M):
            patched, n_asg = re.subn(
                r"^(\s*cai\s+\(mM\))\s*$",
                r"\1\n    cao       (mM)",
                patched,
                count=1,
                flags=re.M,
            )
        target.write_text(patched, encoding="utf-8")
        logs.append(
            f"patched {target.relative_to(model_dir)}: "
            f"removed CONSTANT cao ({n}), ASSIGNED cao ({n_asg})"
        )
    if not logs:
        raise FileNotFoundError(f"no cdp5StCmod.mod under {model_dir}")
    for target in sorted(model_dir.rglob("Hcn1.mod")):
        if is_junk_mod(target):
            continue
        text = _read_backup(target)
        n = text.count("RANGE gbar,r,g, o")
        target.write_text(
            text.replace("RANGE gbar,r,g, o", "RANGE gbar,g, o"), encoding="utf-8"
        )
        logs.append(
            f"patched {target.relative_to(model_dir)}: RANGE gbar,r,g, o -> gbar,g, o ({n})"
        )
    return logs


def patch_105507_batch(model_dir: Path) -> list[str]:
    """sed batch_flag=0, tstop = 1e3, return tti/1e3, print tti/.*"""
    target = model_dir / "batch_.hoc"
    text = _read_backup(target)
    text = text.replace("batch_flag=0", "batch_flag=1")
    text = text.replace("tstop = 1e3", "tstop = 20")
    text = text.replace("return tti/1e3", "return 424242")
    text, n = re.subn(r"print tti/.*", 'print "%some_time%"', text)
    target.write_text(text, encoding="utf-8")
    return [f"patched {target.name}: batch_flag/tstop/tti ({n} print tti lines)"]


SCRIPT_ALLOWLIST = {
    51781: patch_51781_sed_seed,
    97756: patch_97756_startsw,
    97917: patch_97917_mkdll,
    105507: patch_105507_batch,  # Linux yaml only; Windows skip is WINDOWS_SKIP
    124291: patch_124291_ichan2,
    266806: patch_266806_cao_constant,
}

# Windows-only. Do not put these in modeldb-run.yaml skip: true (Linux GHA
# gout is the gold). Lytton vecst/stats/misc VERBATIM is POSIX (sys/time.h,
# drand48, pthread). Not an nrniv.dll extract; not a ModelDB PR this project.
WINDOWS_SKIP = {
    105507: "Lytton VERBATIM POSIX: sys/time.h, drand48, pthread",
    138379: "Lytton VERBATIM POSIX: sys/time.h, drand48, pthread",
}


def load_run_yaml(path: Path) -> dict:
    if yaml is None:
        raise RuntimeError("PyYAML is required (pip install pyyaml)")
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    # yaml keys may be int
    out = {}
    for k, v in data.items():
        try:
            out[int(k)] = v or {}
        except (TypeError, ValueError):
            continue
    return out


def zip_model_dir(zip_path: Path, dest_id_dir: Path) -> Path:
    """Match runmodels: extractall under <workdir>/<id>/; model_dir is that plus
    dirname of the first zip entry."""
    dest_id_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        first = zf.infolist()[0].filename
        inner = os.path.dirname(first)
        model_dir = dest_id_dir / inner if inner else dest_id_dir
        zf.extractall(dest_id_dir)
    return model_dir.resolve()


def find_mosinit(model_dir: Path) -> Path | None:
    found = list(model_dir.rglob("mosinit.hoc"))
    found = [p for p in found if "__MACOSX" not in p.parts]
    found.sort(key=lambda p: (len(p.parts), str(p).lower()))
    return found[0] if found else None


def collect_mod_groups(
    model_dir: Path, start_dir: Path, yaml_model_dir
) -> list[list[Path]]:
    """Directories grouped the way runmodels groups them for one nrnivmodl.

    A yaml list item may be semicolon-separated dirs compiled together
    (156120: mods/other_mods;mods/synapse). Without yaml model_dir, each
    directory under start_dir that contains *.mod is its own group.
    """
    if yaml_model_dir:
        raw = yaml_model_dir
        items = [raw] if isinstance(raw, str) else list(raw)
        groups: list[list[Path]] = []
        for item in items:
            dirs = []
            for part in str(item).split(";"):
                part = part.strip()
                if not part:
                    continue
                d = (model_dir / part).resolve()
                if not d.is_dir():
                    raise FileNotFoundError(f"model_dir {d} does not exist")
                dirs.append(d)
            if dirs:
                groups.append(dirs)
        return groups
    groups = []
    for root, dirnames, filenames in os.walk(start_dir):
        dirnames[:] = [
            d for d in dirnames if d != "__MACOSX" and not d.startswith("._")
        ]
        mods = [
            n
            for n in filenames
            if n.lower().endswith(".mod") and not n.startswith("._")
        ]
        if mods:
            groups.append([Path(root)])
    return groups


def argv_for_windows(cmd: list[str]) -> list[str]:
    """CreateProcess does not apply PATHEXT; .cmd/.bat need cmd.exe /c."""
    if not cmd:
        return cmd
    exe = cmd[0]
    if os.name == "nt" and exe.lower().endswith((".cmd", ".bat")):
        return ["cmd.exe", "/c"] + cmd
    return cmd


def run_captured(cmd, cwd: Path, env: dict, timeout: float) -> dict:
    t0 = time.perf_counter()
    argv = argv_for_windows(cmd)
    try:
        sp = subprocess.run(
            argv,
            cwd=str(cwd),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
        )
        out = sp.stdout.decode("utf-8", errors="replace")
        rc = sp.returncode
        timed_out = False
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or b"").decode("utf-8", errors="replace")
        out += f"\nTIMEOUT after {timeout}s: {cmd!r}"
        rc = -1
        timed_out = True
    except Exception:
        out = traceback.format_exc()
        rc = -1
        timed_out = False
    return {
        "cmd": cmd,
        "cwd": str(cwd),
        "rc": rc,
        "seconds": time.perf_counter() - t0,
        "timeout": timed_out,
        "output": out.splitlines(),
    }


def write_driver_hoc(model_dir: Path, run_lines: list[str] | None) -> Path:
    driver = model_dir / "driver.hoc"
    header = f'\nstrdef verify_dir_ \nverify_dir_ = "{posix(model_dir)}"\n'
    body = header + DRIVER_HOC_BODY
    if run_lines:
        body += "\n" + "\n".join(run_lines) + "\n"
    driver.write_text(body, encoding="utf-8")
    return driver


def find_nrnmech_dll(start_dir: Path) -> Path | None:
    direct = start_dir / "nrnmech.dll"
    if direct.is_file():
        return direct
    # some layouts drop it next to the mods
    for p in start_dir.rglob("nrnmech.dll"):
        if "__MACOSX" not in p.parts:
            return p
    return None


def gout_info(model_dir: Path) -> dict:
    gout = model_dir / "gout"
    if not gout.is_file():
        return {"path": None, "exists": False, "nlines": 0, "head": None}
    raw = gout.read_bytes()
    # keep file as-is; host compare will ignore CRLF
    text = raw.decode("utf-8", errors="replace")
    lines = text.splitlines()
    return {
        "path": str(gout),
        "exists": True,
        "nlines": len(lines),
        "nbytes": len(raw),
        "crlf": b"\r\n" in raw,
        "head": lines[0] if lines else None,
    }


def child_env(neuron_prefix: str | None = None) -> dict:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    # never pick setup.exe 9.0.1
    path = env.get("PATH", "")
    parts = [p for p in path.split(os.pathsep) if p and r"C:\nrn" not in p.lower()]
    prefix = Path(neuron_prefix) if neuron_prefix else None
    if prefix:
        # VS multi-config probe: bin/RelWithDebInfo; install prefix: bin.
        candidates = [
            prefix / "bin" / "RelWithDebInfo",
            prefix / "RelWithDebInfo",
            prefix / "bin",
            prefix,
        ]
        bindir = next((c for c in candidates if (c / "nrniv.exe").is_file() or (c / "nrniv.EXE").is_file()), prefix / "bin")
        parts = [str(bindir)] + parts
        nh = prefix / "share" / "nrn"
        env["NEURONHOME"] = str(nh if nh.is_dir() else prefix)
        env["NRNHOME"] = str(prefix)
        env["CMAKE_PREFIX_PATH"] = str(prefix)
        units = nh / "lib" / "nrnunits.lib"
        if units.is_file():
            env.setdefault("MODLUNIT", str(units))
    else:
        env.pop("NEURONHOME", None)
    env["PATH"] = os.pathsep.join(parts)
    return env


def _mod_files_in(dirs: list[Path]) -> list[str]:
    mods = []
    for d in dirs:
        if d.is_file() and d.suffix.lower() == ".mod":
            mods.append(posix(d))
            continue
        mods.extend(
            posix(p)
            for p in sorted(d.glob("*.mod"))
            if not p.name.startswith("._")
        )
    return mods


def compile_nrnmech_cmake(
    mod_files: list[str],
    cwd: Path,
    env: dict,
    prefix: Path,
    timeout: float,
) -> dict:
    """nrnivmodl via the probe's neuron CMake package (RelWithDebInfo).

    The wheel wrapper hardcodes --config Release and NRNHOME of the pip
    prefix. Probe binaries live in bin/RelWithDebInfo.
    """
    cmake = shutil.which("cmake", path=env.get("PATH"))
    if not cmake:
        return {
            "cmd": ["cmake"],
            "cwd": str(cwd),
            "rc": -1,
            "seconds": 0,
            "timeout": False,
            "output": ["cmake not found on PATH"],
        }
    srcdir = prefix / "lib" / "cmake" / "neuron" / "nrnivmodl"
    builddir = cwd / platform.machine()
    cfg = [
        cmake,
        "-S",
        posix(srcdir),
        "-B",
        posix(builddir),
        f"-DNRNIVMODL_MOD_FILES={';'.join(mod_files)}",
        "-DNRNIVMODL_NEURON=ON",
        "-DNRNIVMODL_CORENEURON=OFF",
        "-DNRNIVMODL_SPECIAL=OFF",
        f"-DCMAKE_PREFIX_PATH={posix(prefix)}",
        "-A",
        "x64",
    ]
    one = run_captured(cfg, cwd, env, timeout)
    if one["rc"] != 0 or one["timeout"]:
        return one
    build = [
        cmake,
        "--build",
        posix(builddir),
        "--parallel",
        "--config",
        "RelWithDebInfo",
    ]
    two = run_captured(build, cwd, env, timeout)
    two["output"] = one["output"] + two["output"]
    two["seconds"] = one["seconds"] + two["seconds"]
    two["cmd"] = cfg + ["&&"] + build
    if two["rc"] == 0 and not two["timeout"]:
        dest = cwd / "nrnmech.dll"
        for src in (
            builddir / "nrnmech.dll",
            builddir / "RelWithDebInfo" / "nrnmech.dll",
            builddir / "Release" / "nrnmech.dll",
        ):
            if src.is_file():
                if src.resolve() != dest.resolve():
                    shutil.copy2(src, dest)
                two["output"].append(f"nrnivmodl: {dest}")
                break
    return two


def which_tools(env: dict) -> dict:
    return {
        "nrniv": shutil.which("nrniv", path=env.get("PATH")),
        "nrnivmodl": shutil.which("nrnivmodl", path=env.get("PATH")),
        "python": sys.executable,
    }


def run_one(
    model_id: int,
    cache_dir: Path,
    workdir: Path,
    run_instr: dict,
    compile_timeout: float,
    run_timeout: float,
    neuron_prefix: str | None = None,
    compile_launch_only: bool = False,
    skip_if_result: bool = False,
) -> dict:
    rec = {
        "id": model_id,
        "ladder": None,  # nrnivmodl | load | gout | failed-at
        "nrnivmodl": None,
        "dll": None,
        "load": None,
        "run": None,
        "gout": None,
        "error": None,
    }
    instr = run_instr.get(model_id, {})
    if instr.get("skip"):
        rec["ladder"] = "skipped"
        rec["error"] = instr.get("comment", "skip: true")
        return rec
    if instr.get("python"):
        rec["ladder"] = "skipped-python"
        rec["error"] = "python models are out of scope for this thin driver"
        return rec
    if model_id in WINDOWS_SKIP:
        rec["ladder"] = "skipped-verbatim-posix"
        rec["error"] = WINDOWS_SKIP[model_id]
        return rec
    dest = workdir / str(model_id)
    if skip_if_result:
        prev = dest / "result.json"
        if prev.is_file():
            try:
                old = json.loads(prev.read_text(encoding="utf-8"))
                old["skipped_existing"] = True
                return old
            except Exception:
                pass
    zip_path = cache_dir / f"{model_id}.zip"
    if not zip_path.is_file():
        rec["error"] = f"missing cache zip {zip_path}"
        rec["ladder"] = "failed-missing-zip"
        return rec
    if dest.exists():
        shutil.rmtree(dest)
    try:
        model_dir = zip_model_dir(zip_path, dest)
    except Exception:
        rec["error"] = traceback.format_exc()
        rec["ladder"] = "failed-unzip"
        return rec
    rec["model_dir"] = str(model_dir)

    logs = []
    if "script" in instr:
        fn = SCRIPT_ALLOWLIST.get(model_id)
        if fn is None:
            if compile_launch_only:
                logs.append(
                    "yaml script present and not allowlisted; skipped for compile+launch"
                )
            else:
                rec["ladder"] = "skipped-untranslated-script"
                rec["error"] = (
                    f"yaml script present and not allowlisted: {instr['script']}"
                )
                return rec
        else:
            try:
                logs.extend(fn(model_dir))
            except Exception:
                rec["error"] = traceback.format_exc()
                rec["ladder"] = "failed-script"
                return rec
    rec["script_logs"] = logs

    run_lines = instr.get("run", DEFAULT_RUN)
    if run_lines is None:
        rec["ladder"] = "compile-only-yaml"
        run_lines = []
    write_driver_hoc(model_dir, run_lines if run_lines else None)
    mosinit = find_mosinit(model_dir)
    start_dir = mosinit.parent if mosinit else model_dir
    rec["start_dir"] = str(start_dir)
    rec["init"] = str(mosinit) if mosinit else None
    rec["driver"] = str(model_dir / "driver.hoc")

    env = child_env(neuron_prefix)
    rec["neuron_prefix"] = neuron_prefix
    rec["tools"] = which_tools(env)
    rec["tools"]["cmake"] = shutil.which("cmake", path=env.get("PATH"))
    if not rec["tools"]["nrniv"]:
        rec["error"] = f"nrniv not on PATH: {rec['tools']}"
        rec["ladder"] = "failed-tools"
        return rec

    try:
        mod_groups = collect_mod_groups(
            model_dir, start_dir, instr.get("model_dir")
        )
    except Exception:
        rec["error"] = traceback.format_exc()
        rec["ladder"] = "failed-mod-dirs"
        return rec
    rec["mod_dirs"] = [[str(d) for d in g] for g in mod_groups]

    # --- ladder 1: nrnivmodl (skip when the zip has no .mod files) ---
    if not mod_groups:
        rec["nrnivmodl"] = {
            "rc": 0,
            "skipped": True,
            "output": ["no .mod files; hoc-only launch"],
        }
        rec["dll"] = None
        nrniv = rec["tools"]["nrniv"]
        load = run_captured(
            [nrniv, "-nobanner", "-c", "quit()"],
            start_dir,
            env,
            min(120.0, run_timeout),
        )
        rec["load"] = load
        rec["load_used_dll_flag"] = False
        if load["rc"] != 0 or load["timeout"]:
            rec["ladder"] = "failed-load"
            rec["error"] = f"nrniv load rc={load['rc']} timeout={load['timeout']}"
            return rec
        rec["ladder"] = "compile+launch"
        rec["gout"] = gout_info(model_dir)
        return rec

    if neuron_prefix:
        if not rec["tools"]["cmake"]:
            rec["error"] = f"cmake not on PATH for probe nrnivmodl: {rec['tools']}"
            rec["ladder"] = "failed-tools"
            return rec
    elif not rec["tools"]["nrnivmodl"]:
        rec["error"] = f"nrnivmodl not on PATH: {rec['tools']}"
        rec["ladder"] = "failed-tools"
        return rec
    compile_out = []
    compile_rc = 0
    compile_secs = 0.0
    last_timeout = False
    last_cmd = None
    for group in mod_groups:
        # One directory: pass the dir (Windows nrnivmodl Test 4).
        # Several directories in one yaml group (156120 semicolon): pass
        # the *.mod files. Two dir args are treated as missing .mod files.
        if len(group) == 1 and not neuron_prefix:
            args = [posix(group[0])]
        else:
            args = _mod_files_in(group)
            if not args:
                rec["error"] = f"no .mod files in {group}"
                rec["ladder"] = "failed-nrnivmodl"
                return rec
        if neuron_prefix:
            one = compile_nrnmech_cmake(
                args, start_dir, env, Path(neuron_prefix), compile_timeout
            )
            cmd = one.get("cmd")
        else:
            cmd = [rec["tools"]["nrnivmodl"]] + args
            one = run_captured(cmd, start_dir, env, compile_timeout)
        last_cmd = cmd
        compile_out.extend(one["output"])
        compile_secs += one["seconds"]
        compile_rc = one["rc"]
        last_timeout = one["timeout"]
        if compile_rc != 0 or one["timeout"]:
            rec["nrnivmodl"] = {
                "cmd": cmd,
                "cwd": str(start_dir),
                "rc": compile_rc,
                "seconds": compile_secs,
                "timeout": one["timeout"],
                "output": compile_out,
            }
            rec["ladder"] = "failed-nrnivmodl"
            rec["error"] = f"nrnivmodl rc={compile_rc} timeout={one['timeout']}"
            return rec
    rec["nrnivmodl"] = {
        "cmd": last_cmd,
        "cwd": str(start_dir),
        "rc": compile_rc,
        "seconds": compile_secs,
        "timeout": last_timeout,
        "output": compile_out,
    }
    dll = find_nrnmech_dll(start_dir)
    rec["dll"] = str(dll) if dll else None
    if dll is None:
        rec["ladder"] = "failed-nrnivmodl"
        rec["error"] = "nrnivmodl rc=0 but nrnmech.dll not found"
        return rec

    # --- ladder 2: launch + load ---
    nrniv = rec["tools"]["nrniv"]
    load_cmd = [nrniv, "-nobanner", "-c", "quit()"]
    load = run_captured(load_cmd, start_dir, env, min(120.0, run_timeout))
    rec["load"] = load
    loaded = load["rc"] == 0 and not load["timeout"]
    used_dll_flag = False
    if not loaded:
        dll_arg = posix(dll)
        load_cmd = [nrniv, "-nobanner", "-dll", dll_arg, "-c", "quit()"]
        load = run_captured(load_cmd, start_dir, env, min(120.0, run_timeout))
        rec["load"] = load
        rec["load"]["dll_flag"] = dll_arg
        used_dll_flag = True
        loaded = load["rc"] == 0 and not load["timeout"]
    rec["load_used_dll_flag"] = used_dll_flag
    if not loaded:
        rec["ladder"] = "failed-load"
        rec["error"] = f"nrniv load rc={load['rc']} timeout={load['timeout']}"
        return rec

    if compile_launch_only:
        rec["ladder"] = "compile+launch"
        rec["gout"] = gout_info(model_dir)
        return rec

    if not run_lines:
        rec["ladder"] = "compile+launch"
        rec["gout"] = gout_info(model_dir)
        return rec

    if mosinit is None:
        rec["ladder"] = "compile+launch"
        rec["error"] = "no mosinit.hoc; skipped full run"
        rec["gout"] = gout_info(model_dir)
        return rec

    # --- ladder 3: run + gout ---
    run_cmd = [nrniv, "-nobanner"]
    if used_dll_flag:
        run_cmd += ["-dll", posix(dll)]
    run_cmd += [posix(mosinit), posix(model_dir / "driver.hoc")]
    run = run_captured(run_cmd, start_dir, env, run_timeout)
    rec["run"] = {
        "cmd": run["cmd"],
        "cwd": run["cwd"],
        "rc": run["rc"],
        "seconds": run["seconds"],
        "timeout": run["timeout"],
        "output": run["output"],
    }
    rec["gout"] = gout_info(model_dir)
    if run["timeout"] or run["rc"] != 0:
        rec["ladder"] = "failed-run"
        rec["error"] = f"nrniv run rc={run['rc']} timeout={run['timeout']}"
        return rec
    if not rec["gout"]["exists"]:
        rec["ladder"] = "compile+launch"  # ran, but no gout (Graph/SSH?)
        rec["error"] = "run rc=0 but gout missing"
        return rec
    rec["ladder"] = "gout"
    return rec


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cache", required=True, help="directory of <id>.zip")
    ap.add_argument("--workdir", required=True, help="C: workdir (not vboxsf)")
    ap.add_argument("--yaml", required=True, help="modeldb-run.yaml")
    ap.add_argument("--compile-timeout", type=float, default=900)
    ap.add_argument("--run-timeout", type=float, default=600)
    ap.add_argument(
        "--neuron-prefix",
        default="",
        help="Probe install (e.g. C:\\nrn-probe). Empty: PATH nrniv/nrnivmodl (wheel).",
    )
    ap.add_argument(
        "--compile-launch-only",
        action="store_true",
        help="Stop after nrnivmodl + nrniv load. Do not run mosinit/gout.",
    )
    ap.add_argument(
        "--skip-if-result",
        action="store_true",
        help="Reuse workdir/<id>/result.json when present (resume a sweep).",
    )
    ap.add_argument(
        "--ids-file",
        default="",
        help="Text file of model ids (one per line or whitespace-separated).",
    )
    ap.add_argument("ids", nargs="*", type=int)
    args = ap.parse_args(argv)
    ids = list(args.ids)
    if args.ids_file:
        text = Path(args.ids_file).read_text(encoding="utf-8")
        ids.extend(int(tok) for tok in text.split() if tok.strip())
    if not ids:
        ap.error("need ids arguments and/or --ids-file")
    # keep order, drop dupes
    seen = set()
    uniq = []
    for mid in ids:
        if mid not in seen:
            seen.add(mid)
            uniq.append(mid)
    ids = uniq

    os.environ.pop("PYTHONPATH", None)
    prefix = args.neuron_prefix or None
    if not prefix:
        os.environ.pop("NEURONHOME", None)

    cache_dir = Path(args.cache)
    workdir = Path(args.workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    run_instr = load_run_yaml(Path(args.yaml))

    env0 = child_env(prefix)
    summary = {
        "python": sys.executable,
        "neuron_prefix": prefix,
        "compile_launch_only": args.compile_launch_only,
        "nrnversion": None,
        "neuronhome": env0.get("NEURONHOME"),
        "nrniv": env0 and shutil.which("nrniv", path=env0.get("PATH")),
        "nrnivmodl": env0 and shutil.which("nrnivmodl", path=env0.get("PATH")),
        "models": [],
    }
    nrniv = summary["nrniv"]
    if nrniv:
        ver = run_captured(
            [nrniv, "-nobanner", "-c", "print nrnversion()", "-c", "quit()"],
            Path("."),
            env0,
            30,
        )
        summary["nrnversion_output"] = (ver.get("output") or [])[:20]
        for line in ver.get("output") or []:
            if "VERSION" in line or "nrnversion" in line.lower():
                summary["nrnversion"] = line.strip()
                break

    for mid in ids:
        print(f"=== model {mid} ===", flush=True)
        rec = run_one(
            mid,
            cache_dir,
            workdir,
            run_instr,
            args.compile_timeout,
            args.run_timeout,
            neuron_prefix=prefix,
            compile_launch_only=args.compile_launch_only,
            skip_if_result=args.skip_if_result,
        )
        summary["models"].append(rec)
        outp = workdir / str(mid) / "result.json"
        outp.parent.mkdir(parents=True, exist_ok=True)
        outp.write_text(json.dumps(rec, indent=2), encoding="utf-8")
        print(
            f"id={mid} ladder={rec.get('ladder')} dll={rec.get('dll')} "
            f"gout={rec.get('gout')} error={rec.get('error')}",
            flush=True,
        )
        (workdir / "summary.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )

    print("WROTE", workdir / "summary.json", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
