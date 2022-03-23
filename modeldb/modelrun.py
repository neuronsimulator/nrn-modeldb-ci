import logging
import multiprocessing
import subprocess
import os
import sys
from .progressbar import ProgressBar
from .data import Model
from . import modeldb
from .config import *
from .hocscripts import *
import zipfile
import glob
import traceback
import json
import time
import shutil

ModelDB = modeldb.ModelDB()


def is_dir_non_empty(directory):
    """
    Returns True if the `directory` exists and is non-empty
    """
    try:
        if any(os.scandir(directory)):
            return True
    except Exception:  # noqa
        pass

    return False


class ModelRun(dict):
    def __init__(self, model, working_dir, clean=False):
        self._model = model
        self._working_dir = os.path.abspath(working_dir)
        self._logs = []
        self._gout = []
        self._nrn_run = []
        self._nrn_run_error = False
        self._no_mosinit_hoc = False
        self._run_time = 0
        self._run_py = False
        self._clean = clean

        self["run_info"] = {}

        self._fetch_model()

    def _fetch_model(self):
        # get run instruction from ModelDB
        if self.id in ModelDB.run_instr:
            self.update(ModelDB.run_instr[self.id])

        # check if model is run in Python
        if "python" in self:
            self._run_py = True
        # if no actual run instructions are specified, add default run command
        if "run" not in self:
            if self.run_py:
                self["run"] = ["python mosinit.py"]
            else:
                self["run"] = ["verify_graph_()"]

    run_info = property(lambda self: self["run_info"])

    logs = property(lambda self: self._logs)
    gout = property(lambda self: self._gout)
    nrn_run = property(lambda self: self._nrn_run)
    no_mosinit_hoc = property(lambda self: self._no_mosinit_hoc)
    run_py = property(lambda self: self._run_py)

    nrn_run_error = property(lambda self: self._nrn_run_error)
    model_dir = property(lambda self: self.run_info["model_dir"] if "model_dir" in self.run_info else "")
    working_dir = property(lambda self: self._working_dir)
    run_time = property(lambda self: self._run_time)

    id = property(lambda self: self._model.id)


def curate_log_string(model, logstr):
    return logstr.replace(model.model_dir, '%model_dir%') if len(model.model_dir) else logstr


def append_log(model, model_sink, text):
    model_sink.extend(curate_log_string(model, text).split('\n'))


def run_commands(model, cmds, work_dir=None):
    out, _ = subprocess.Popen(
            cmds,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            cwd=model.model_dir if work_dir is None else work_dir,
        ).communicate()

    model.logs.extend(curate_log_string(model, out).split('\n'))


def run_neuron_cmds(model, cmds):
    sp = subprocess.Popen(
        cmds,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        cwd=model.run_info["start_dir"],
    )
    out, _ = sp.communicate()

    model.nrn_run.extend(curate_log_string(model, out).split('\n'))
    if sp.returncode > 1:
        model._nrn_run_error = True


def clean_model_dir(model):
    # delete x86_64 folder
    run_commands(model, ["/bin/sh", "-c", "rm -rf ./x86_64/"], work_dir=model.run_info["start_dir"])


def compile_mods(model, mods):
    run_commands(model, ["nrnivmodl"] + mods, work_dir=model.run_info["start_dir"])


def build_driver_hoc(model):
    model.run_info["driver"] = os.path.join(model.model_dir, "driver.hoc")

    with open(model.run_info["driver"], "w") as drv:
        drv.write(driver_hoc_header.format(model_dir=model.model_dir))
        drv.writelines(driver_hoc_body)
        if model["run"] is not None:
            drv.writelines("\n".join(model["run"]))  # how to run the model


def build_quit_hoc(model):
    model.run_info["start_dir"] = model.model_dir

    with open(os.path.join(model.model_dir, "quit.hoc"), "w") as qt:
        qt.write(quit_hoc)

    model.run_info["init"] = os.path.join(model.model_dir, "quit.hoc")


def select_mosinit(model):
    # look for `mosinit.hoc`. It could also be produced by `init` script above
    mosfiles = glob.glob(model.model_dir + "/**/mosinit.hoc", recursive=True)
    mosfiles.sort()
    if len(mosfiles):
        model.run_info["start_dir"] = os.path.dirname(os.path.join(model.model_dir, mosfiles[0]))
        model.run_info["init"] = mosfiles[0]
    else:
        build_quit_hoc(model)
        model._no_mosinit_hoc = True


def build_and_run_script(model):
    if "script" in model:
        with open(os.path.join(model.model_dir, "script.tmp"), "w") as script:
            script.writelines("\n".join(model["script"]))
            script.flush()
        run_commands(model, ["/bin/sh", "script.tmp"])
        model.run_info["script"] = model["script"]


def build_python_runfile(model):
    model.run_info["start_dir"] = model.model_dir
    with open(os.path.join(model.model_dir, "model_run.py"), "w") as script:
        script.writelines("\n".join(model["run"]))
        script.flush()
    model.run_info["init"] = "model_run.py"
    model.run_info["driver"] = ""


def prepare_model(model):
    # unzip model from cache
    with zipfile.ZipFile(
            os.path.join(MODELS_ZIP_DIR, str(model.id) + ".zip"), "r"
    ) as zip_ref:
        model_dir = os.path.join(
            model.working_dir, os.path.dirname(zip_ref.infolist()[0].filename)
        )
        if model._clean and is_dir_non_empty(model_dir):
            shutil.rmtree(model_dir)
        zip_ref.extractall(model.working_dir)
        model.run_info["model_dir"] = model_dir

    # write driver.hoc
    build_driver_hoc(model)

    # write and execute extra script if specified in the run instructions
    build_and_run_script(model)

    # Determine init file: HOC or Python.
    # Python
    if model.run_py:
        build_python_runfile(model)
    # HOC: If 'run' is None -> quit.hoc (DoNotRun = yes) else look for 'mosinit.hoc'
    elif model["run"] is None:
        build_quit_hoc(model)
    else:
        select_mosinit(model)
    if model["run"] is None:
        append_log(model, model.logs,
            "Model in do not run mode according to modeldb-run.yaml:\n\t{}\n".format(
                model["comment"]
            )
        )


def run_model(model):
    start_time = time.perf_counter()
    # Some models are skipped on purpose
    if "skip" in model:
        append_log(model, model.logs,
            "Model is skipped according to modeldb-run.yaml:\n\t{}\n".format(
                model["comment"]
            )
        )
        return model
    mods = None

    try:
        # prepare model
        prepare_model(model)

        # Get mod files. Model can have a custom mod directory or directories, otherwise we search in the start_dir
        if "model_dir" in model:
            mods = []
            for moddir in model["model_dir"].split(';'):
                mod_pattern = os.path.join(model.model_dir, moddir) + "/*.mod"
                mods.extend(glob.glob(mod_pattern))
        else:
            mod_pattern = model.run_info["start_dir"] + "/*.mod"
            mods = glob.glob(mod_pattern)
        # compile mods if available
        if len(mods):
            # in case of reruns
            clean_model_dir(model)
            # translate them to cpp
            compile_mods(model, mods)

    except Exception:  # noqa
        append_log(model, model.logs, traceback.format_exc())

    # run NEURON
    try:
        nrn_exe = "./x86_64/special" if mods is not None and len(mods) else "nrniv"
        # '-nogui' creates segfault
        model_run_cmds = [nrn_exe, '-nobanner']
        if model.run_py:
            model_run_cmds.append('-python')
        model_run_cmds += [model.run_info["init"], model.run_info["driver"]]
        append_log(model, model.nrn_run, "RUNNING -> {}".format(" ".join(model_run_cmds)))
        run_neuron_cmds(model, model_run_cmds)
        if os.path.isfile(os.path.join(model.model_dir, "gout")):
            with open(os.path.join(model.model_dir, "gout"), 'r') as gout:
                model._gout = gout.readlines()
    except Exception:  # noqa
        append_log(model, model.nrn_run, traceback.format_exc())
        model._nrn_run_error = True

    stop_time = time.perf_counter()

    model._run_time = str(stop_time - start_time)

    return model


class ModelRunManager(object):
    def __init__(self, master_dir, gout=False, clean=False):
        self.master_dir = master_dir
        self.logfile = str(master_dir) + ".log"
        self.dumpfile = str(master_dir) + ".json"
        self._setup_logging()
        self.logger.info(
            "Initialized -> logfile: " + self.logfile
        )
        self.run_logs = {}
        self._gout = gout
        self._clean = clean

    def _setup_logging(self):
        self.logger = logging.getLogger("dev")
        self.logger.setLevel(logging.DEBUG)
        self.logFormatter = logging.Formatter(
            fmt="%(asctime)s :: %(levelname)-8s :: %(message)s"
        )

        self.fileHandler = logging.FileHandler(self.logfile)
        self.fileHandler.setFormatter(self.logFormatter)
        self.fileHandler.setLevel(logging.DEBUG)

        self.consoleHandler = logging.StreamHandler()
        self.consoleHandler.setFormatter(self.logFormatter)
        self.consoleHandler.setLevel(logging.INFO)

        self.logger.addHandler(self.fileHandler)
        self.logger.addHandler(self.consoleHandler)

    def _grep_for_errors(self):
        if len(self.run_logs):
            self.logger.info("Grepping all models for ' error:' and dumping run errors")

            for model_id, logs in self.run_logs.items():
                mod_errors = list(filter(lambda x: " error:" in x, logs["logs"]))
                if len(mod_errors) > 0:
                    self.run_logs[model_id]["moderr"] = mod_errors
                    self.logger.error(
                        str(model_id) + "\n\t" + "\t".join(mod_errors)
                    )
                if "nrn_run_err" in logs and logs["nrn_run_err"] is True:
                    self.logger.error(
                        str(model_id) + "\n\t" + "\t".join(logs["nrn_run"])
                    )

    def _dump_run(self):
        self.logger.info("Dumping run logs to {} ...".format(self.dumpfile))

        # Run info, use key 0
        self.run_logs[0] = {}
        from neuron import __version__ as nrn_ver
        self.run_logs[0]["NEURON version"] = nrn_ver
        self.run_logs[0]["Stats"] = self._run_stats(self.run_logs)

        # Dump logs
        with open(self.dumpfile, "w+") as dump_file:
            json.dump(self.run_logs, dump_file, indent=4, sort_keys=True)

    @staticmethod
    def _run_stats(json_report):
        stats = {}
        stats["Total nof models run"] = len(json_report) - 1  # discard 0
        failed_mods = []
        failed_runs = []
        skipped_runs = []
        
        for model_id in json_report.keys():
            # look for models that are marked `skip` in `modeldb-run.yaml`
            if "do_not_run" in json_report[model_id]:
                skipped_runs.append(model_id)

            # moderr happens if mods present and nrnivmodl failed
            # if no moderr we look for nrn_run_err    
            if "moderr" in json_report[model_id]:
                failed_mods.append(model_id)
            elif "nrn_run_err" in json_report[model_id]:
                failed_runs.append(model_id)

        stats["Failed models"] = {"Count": len(failed_mods),
                                "Accession numbers": failed_mods}

        stats["Failed runs"] = {"Count": len(failed_runs),
                                "Accession numbers": failed_runs}

        stats["Skipped runs"] = {"Count": len(skipped_runs),
                                "Accession numbers": skipped_runs}

        return stats


    def _run_models(self, model_runs):
        pool = multiprocessing.Pool()

        processed_models = pool.imap_unordered(run_model, model_runs)
        for model in ProgressBar.iter(processed_models, self.nof_models):
            self.run_logs[model.id] = {}
            self.run_logs[model.id]["logs"] = model.logs
            if self._gout:
                self.run_logs[model.id]["gout"] = model.gout
            self.run_logs[model.id]["nrn_run"] = model.nrn_run
            if "skip" in model:
                self.run_logs[model.id]["do_not_run"] = True
            if model.nrn_run_error:
                self.run_logs[model.id]["nrn_run_err"] = True
            if model.no_mosinit_hoc:
                self.run_logs[model.id]["no_mosinit_hoc"] = True
            self.run_logs[model.id]["run_info"] = model.run_info
            self.run_logs[model.id]["run_time"] = model.run_time
            self.logger.debug("Done for: " + str(model.id))

        self._grep_for_errors()
        self._dump_run()

    def run_models(self, model_list=None):
        self.logger.info(
            "Master directory is: " + self.master_dir
        )

        if not os.path.isdir(self.master_dir):
            self.logger.info("Creating master directory...")
            os.mkdir(self.master_dir)

        # models selection
        models_selected = (
            ModelDB.metadata.values()
            if model_list is None
            else (ModelDB.metadata[k] for k in model_list)
        )

        # prepare ModelRun objects
        models_to_run = (
            ModelRun(mdl, self.master_dir, self._clean) for mdl in models_selected
        )

        # number of models
        self.nof_models = (
            len(ModelDB.metadata) if model_list is None else len(model_list)
        )

        self.logger.info("Running models ...")
        self.logger.info(
            "\t\t-> number of models: " + str(self.nof_models)
        )
        self._run_models(models_to_run)
        self.logger.info("Done.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(
            "Need to specify master directory " "containing the different model folders"
        )
        sys.exit(1)

    ModelRunManager(sys.argv[1]).run_models()
