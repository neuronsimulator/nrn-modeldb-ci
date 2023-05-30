import logging
from docopt import docopt
from os.path import abspath
from pprint import pprint
from . import config
from .modelrun import ModelRunManager, is_dir_non_empty
from .modeldb import ModelDB
import inspect
import shlex
import subprocess
from jinja2 import Environment, FileSystemLoader
import os
import sys
from .config import *
from pathlib import Path
from .report import diff_reports
import json
import shutil


def runmodels(args=None):
    """runmodels

    Run nrn-modeldb-ci for all or specified models

    Usage:
        runmodels --workdir=<PATH> [options] [<model_id>...]
        runmodels -h    Print help

    Arguments:
        --workdir=<PATH>          Required: directory where to run the models and store the reports
        model_id=<n>            Optional: ModelDB accession number(s) to run; default is all available models

    Options:
        --gout                  Include gout into the report. Note that gout data can be very big, so disabled by default.
        --virtual               Run in headless mode. You need a back-end like Xvfb.
        --clean                 Auto-clean model working directory before running (useful for consecutive runs and failsafe)
        --norun                 Compile and link only (nrnivmodl).
        --inplace               Skip model preparation logic, simply run NEURON.

    Examples
        runmodels --workdir=/path/to/workdir                        # run all models
        runmodels --clean --workdir=/path/to/workdir 23613 12344    # run models 23613 & 12344
    """
    options = docopt(runmodels.__doc__, args)
    working_dir = options.pop("--workdir")
    model_ids = [int(model_id) for model_id in options.pop("<model_id>")]
    gout = options.pop("--gout", False)
    virtual = options.pop("--virtual", False)
    clean = options.pop("--clean", False)
    norun = options.pop("--norun", False)
    inplace = options.pop("--inplace", False)

    if os.path.abspath(working_dir) == ROOT_DIR:
        print("Cannot run models directly into nrn-modeldb-ci ROOT_DIR -> {}".format(ROOT_DIR))
        sys.exit(1)

    if clean and inplace:
        print("ERROR: --clean and --inplace are mutually exclusive")
        sys.exit(1)

    if not (clean or inplace) and is_dir_non_empty(working_dir):
        print("ERROR: WorkingDirectory {} exists and is non empty.".format(working_dir))
        print("\t re-run with one of these options:\n"
              "\t\t--clean \t-> if you wish to OVERWRITE model runs (delete content from --workdir and re-build from cache)\n"
              "\t\t--inplace \t-> if you wish to re-run the same model (content in --workdir is kept)\n")
        sys.exit(1)

    mrm = ModelRunManager(working_dir, gout=gout, clean=clean, norun=norun, inplace=inplace)
    model_list = model_ids if model_ids else None

    if virtual:
        from pyvirtualdisplay import Display
        with Display(manage_global_env=True, visible=False) as _:
            mrm.run_models(model_list)
    else:
        mrm.run_models(model_list)


def getmodels(args=None):
    """getmodels

    Retrieve all or specified models from ModelDB.

    Usage:
        getmodels [<model_id>...]
        getmodels -h

    Arguments:
        model_id=<n>           Optional: ModelDB accession number(s) to download; default is all available models

    Examples
        getmodels
        getmodels 23613 12344
    """
    options = docopt(getmodels.__doc__, args)
    model_ids = [int(model_id) for model_id in options.pop("<model_id>")]

    mdb = ModelDB()
    mdb.download_models(model_list=model_ids if model_ids else None)


def diffgout(args=None):
    """diffgout

        Graphically compare two gout files

    Usage:
        diffgout <goutFile1> <goutFile2>
        diffgout -h         Print help

    Arguments:
        goutFile1=PATH      Required: file path to first gout file
        goutFile2=PATH      Required: file path to second gout file

    Examples
        diffgout 3246-master/varela/gout 3246-8.0.2/varela/gout

    """
    options = docopt(diffgout.__doc__, args)

    gout_file1 = options.pop("<goutFile1>")
    gout_file2 = options.pop("<goutFile2>")

    cmd = 'nrngui -c "strdef gout1" -c "gout1=\\"{}\\"" -c "strdef gout2" -c "gout2=\\"{}\\"" modeldb/showgout.hoc'.format(
        gout_file1, gout_file2)
    commands = shlex.split(cmd)
    _ = subprocess.Popen(commands)


def modeldb_config(args=None):
    """modeldb-config

    Print out ModelDB configuration items

    Usage:
        modeldb-config [options]
        modeldb-config -h    Print help

    Options:
        --item=ARG          Print out value for specific config item

    Examples
        modeldb-config
        modeldb-config --item=MODELS_ZIP_DIR
    """
    options = docopt(modeldb_config.__doc__, args)
    item = options.pop("--item", None)
    cfg_module = globals().get('config', None)
    if item is None:
        pprint({var: getattr(cfg_module, var) for var in dir(cfg_module) if
            not inspect.ismodule(var) and not var.startswith("__") and not var.endswith("__")})
    else:
        print(getattr(cfg_module, item))


def report2html(args=None):
    """report2html

        Create an interactive HTML report from a single run.

    Usage:
        report2html <json_report>
        report2html -h         Print help

    Arguments:
        json_report=PATH      Required: json report file following runmodels

    Examples
        report2html 3246-master.json

    """
    options = docopt(report2html.__doc__, args)

    json_report = options.pop("<json_report>")

    file_loader = FileSystemLoader(os.path.join(Path(__file__).parent.resolve(), 'templates'))
    env = Environment(loader=file_loader)
    template = env.get_template('report.html')

    report_filename = os.path.join(os.path.splitext(os.path.basename(json_report))[0] + '.html')
    print('Writing {} ...'.format(report_filename))
    with open(report_filename, 'w') as fh, open(json_report, 'r+') as jr:
        fh.write(template.render(
            title="{} : nr-modeldb-ci HTML report".format(json_report),
            json_report=json.load(jr),
        ))
    print('Done.')


def diffreports2html(args=None):
    """diffreports2html

        Create an interactive HTML report from two nrn-modeldb-ci json reports.
        Note that you should have the gout files present if you want to diff them.

    Usage:
        diffreports2html <json_report1> <json_report2>
        diffreports2html -h         Print help

    Arguments:
        json_report1=PATH      Required: json report file following runmodels for NEURON version 1
        json_report2=PATH      Required: json report file following runmodels for NEURON version 2

    Examples
        diffreport2html 3246-master.json 3246-8.0.2.json

    """
    options = docopt(diffreports2html.__doc__, args)

    json_report1 = options.pop("<json_report1>")
    json_report2 = options.pop("<json_report2>")

    file_loader = FileSystemLoader(os.path.join(Path(__file__).parent.resolve(), 'templates'))
    env = Environment(loader=file_loader)
    template = env.get_template('diffreport.html')
    runtime_template = env.get_template('runtimes.html')


    report_title = '{}-vs-{}'.format( os.path.splitext(os.path.basename(json_report1))[0],
                                      os.path.splitext(os.path.basename(json_report2))[0] )
    report_filename = os.path.join(Path(json_report1).resolve().parent, report_title + '.html')
    runtime_report_title = 'Runtimes ' + report_title
    runtime_report_filename = os.path.join(Path(json_report1).resolve().parent, "runtimes-" + report_title + '.html')
    diff_dict, gout_dict, runtime_dict, stats_dict, v1, v2 = diff_reports(json_report1, json_report2)

    print('Writing {} ...'.format(report_filename))
    with open(report_filename, 'w') as fh:
        fh.write(template.render(
            title="{}".format(report_title),
            diff_dict=diff_dict,
            gout_dict=gout_dict),
        )
    print('Done.')
    print('Writing {} ...'.format(runtime_report_filename))
    with open(runtime_report_filename, 'w') as fh:
        fh.write(runtime_template.render(
            title="{}".format(runtime_report_title),
            runtime_dict=runtime_dict,
            stats={"stats":diff_dict['0']},
            v1=v1,
            v2=v2),
    )
    print('Done.')
    # Return a useful status code
    code = 0
    if len(diff_dict) > 1:
        assert "0" in diff_dict  # summary info; not a real diff
        print("FAILURE: stdout diffs in {}".format(set(diff_dict.keys()) - {"0"}))
        code = 1
    if len(gout_dict) > 1:
        assert "0" in gout_dict  # summary info; not a real diff
        print("FAILURE: gout diffs in {}".format(set(diff_dict.keys()) - {"0"}))
        code = 1
    total_failures = sum(
        version_stats["Failed models"]["Count"] for version_stats in stats_dict.values()
    )
    if total_failures > 0:
        print(
            "FAILURE: there were {} failed model builds across {} versions of NEURON".format(
                total_failures, len(stats_dict)
            )
        )
        code = 1
    total_runtime_failures = sum(
        version_stats["Failed runs"]["Count"] for version_stats in stats_dict.values()
    )
    if total_runtime_failures > 0:
        print(
            "FAILURE: there were {} failed model runs across {} versions of NEURON".format(
                total_runtime_failures, len(stats_dict)
            )
        )
        code = 1
    # These are not expected to be different between the two NEURON versions tested
    assert (
        len(
            {
                version_stats["Skipped runs"]["Count"]
                for version_stats in stats_dict.values()
            }
        )
        == 1
    )
    assert (
        len(
            {
                version_stats["Total nof models run"]
                for version_stats in stats_dict.values()
            }
        )
        == 1
    )
    return code
