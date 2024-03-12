import json
import re
import difflib
import logging
import os
import shlex
import subprocess
from .modeldb import ModelDB
from pygments import highlight
from pygments.lexers import DiffLexer
from pygments.formatters import HtmlFormatter


mdb = ModelDB()


def curate_run_data(run_data, model=None):
    curated_data = run_data

    regex_dict = {
        # /../nrniv: Assignment to modern physical constant FARADAY	<-> ./x86_64/special: Assignment to modern physical constant FARADAY
        "^/.*?/nrniv:": "%neuron-executable%:",
        "^\\./x86_64/special:": "%neuron-executable%:",
        # nrniv: unable to open font "*helvetica-medium-r-normal*--14*", using "fixed" <-> special: unableto open font "*helvetica-medium-r-normal*--14*", using "fixed"
        "^nrniv:": "%neuron-executable%:",
        "^special:": "%neuron-executable%:",
        "(Mon|Tue|Wed|Thu|Fri|Sat|Sun) (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d+\s+\d+:\d+:\d+ [A-Z\s]+ \d+": "%date_command%",
        "total run time [0-9\.]+": "total run time %run_time%",
        "(^.*distutils.*$)": "",
        "/.*?/lib/python.*/site-packages/": "%python-site-packages%",
    }

    for model_specific_substitution in mdb.run_instr.get(model, {}).get(
        "curate_patterns", []
    ):
        regex_dict[model_specific_substitution["pattern"]] = (
            model_specific_substitution["repl"]
        )

    for regex_key, regex_value in regex_dict.items():
        updated_data = []
        pattern = re.compile(regex_key)
        for line in curated_data:
            new_line, number_of_subs = pattern.subn(regex_value, line)
            if number_of_subs:
                logging.debug("{} matched {} time(s)".format(regex_key, number_of_subs))
                logging.debug("{} -> {}".format(line, new_line))
            # if we are replacing a full line with an empty string, don't add it to the curated data
            if new_line:
                updated_data.append(new_line)
        curated_data = updated_data

    return curated_data


def diff_reports(report1_json, report2_json):
    diff_dict = {}
    gout_dict = {}
    runtime_dict = {}

    with open(report1_json, "r+") as f, open(report2_json, "r+") as f2:
        data_a = json.load(f)
        data_b = json.load(f2)

        hd = difflib.HtmlDiff()
        v1 = data_a["0"]["NEURON version"]
        v2 = data_b["0"]["NEURON version"]
        diff_dict["0"] = hd.make_table(
            json.dumps(data_a["0"], indent="\t").split("\n"),
            json.dumps(data_b["0"], indent="\t").split("\n"),
        ).replace("\n", "")
        stats_dict = {v1: data_a["0"]["Stats"], v2: data_b["0"]["Stats"]}
        for k in data_a.keys():
            if int(k) == 0:
                continue  # skip info key
            if k not in data_b:
                ud_empty = difflib.unified_diff(
                    data_a[k]["nrn_run"],
                    ["Accession number {} not found in report2".format(k)],
                )
                diff_dict[k] = highlight(
                    "\n".join(ud_empty),
                    DiffLexer(),
                    HtmlFormatter(linenos=True, cssclass="colorful", full=True),
                )
                continue
            curated_a = curate_run_data(data_a[k]["nrn_run"], model=int(k))
            curated_b = curate_run_data(data_b[k]["nrn_run"], model=int(k))
            start_dir_a = (
                data_a[k]["run_info"]["start_dir"]
                if "run_info" in data_a[k] and "start_dir" in data_a[k]["run_info"]
                else "unknown"
            )
            start_dir_b = (
                data_b[k]["run_info"]["start_dir"]
                if "run_info" in data_b[k] and "start_dir" in data_b[k]["run_info"]
                else "unknown"
            )
            if curated_a != curated_b:
                ud = difflib.unified_diff(
                    curated_a, curated_b, fromfile=start_dir_a, tofile=start_dir_b
                )
                diff_dict[k] = highlight(
                    "\n".join(ud),
                    DiffLexer(),
                    HtmlFormatter(linenos=True, cssclass="colorful", full=True),
                )

            def _speedup(a, b):
                dict = {}
                dict["v1"] = a
                dict["v2"] = b
                # compute slowdown/speedup relative to runtime_b (negative means slowdown)
                dict["speedup"] = (float(b) - float(a)) / float(b) * 100
                return dict

            # List of keys that make gout comparison and speedup comparison pointless
            skip_keys = {"do_not_run", "moderr", "nrn_run_err"}
            if skip_keys.isdisjoint(data_a[k]) and skip_keys.isdisjoint(data_b[k]):
                # compare runtimes and compute slowdown or speedup
                runtime_dict[k] = {}
                runtime_dict[k]["total"] = _speedup(
                    data_a[k]["run_time"], data_b[k]["run_time"]
                )
                for runkey in ("model", "nrnivmodl"):
                    if (
                        runkey in data_a[k]["run_times"]
                        and runkey in data_b[k]["run_times"]
                    ):
                        runtime_dict[k][runkey] = _speedup(
                            data_a[k]["run_times"][runkey],
                            data_b[k]["run_times"][runkey],
                        )

                # compare gout
                gout_a_file = os.path.join(data_a[k]["run_info"]["start_dir"], "gout")
                gout_b_file = os.path.join(data_b[k]["run_info"]["start_dir"], "gout")
                # gout may be missing in one of the paths. `diff -N` treats non-existent files as empty.
                if os.path.isfile(gout_a_file) or os.path.isfile(gout_b_file):
                    # https://stackoverflow.com/questions/1180606/using-subprocess-popen-for-process-with-large-output
                    diff_cmd = [
                        "diff",
                        "-uN",
                        "--speed-large-files",
                        gout_a_file,
                        gout_b_file,
                    ]
                    child = subprocess.Popen(
                        diff_cmd,
                        bufsize=1,  # line buffered
                        stdout=subprocess.PIPE,  # we read from stdout below
                        shell=False,
                        text=True,
                    )
                    # sometimes when the results are wildly different then diff can ~hang
                    timeout = 2  # seconds
                    try:
                        (diff_out, _) = child.communicate(timeout=timeout)
                        diff_out = diff_out.splitlines()
                        # maximum 30 lines to keep the summary diff page responsive
                        if len(diff_out) > 30:
                            diff_out = "\n".join(
                                diff_out[:30]
                                + [
                                    "... {} lines suppressed ...".format(
                                        len(diff_out) - 30
                                    )
                                ]
                            )
                        else:
                            diff_out = "\n".join(diff_out)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        diff_out = (
                            "{} did not complete in {} seconds, killing it".format(
                                diff_cmd, timeout
                            )
                        )
                    if diff_out:
                        gout_dict[k] = highlight(
                            diff_out,
                            DiffLexer(),
                            HtmlFormatter(linenos=True, cssclass="colorful", full=True),
                        )

    return diff_dict, gout_dict, runtime_dict, stats_dict, v1, v2
