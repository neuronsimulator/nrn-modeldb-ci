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

    if os.path.abspath(working_dir) == ROOT_DIR:
        print("Cannot run models directly into nrn-modeldb-ci ROOT_DIR -> {}".format(ROOT_DIR))
        sys.exit(1)

    if not clean and is_dir_non_empty(working_dir):
        print("WARNING: WorkingDirectory {} exists and is non empty.".format(working_dir))
        print("\tre-run with --clean if you wish to overwrite model runs!")
        sys.exit(1)

    mrm = ModelRunManager(working_dir, gout=gout, clean=clean)
    model_list = model_ids if model_ids else None

    if virtual:
        from pyvirtualdisplay import Display
        with Display() as _:
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
        modeldb-config --item=MDB_NEURON_MODELS_URL
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

    report_filename = os.path.join(os.path.splitext(json_report)[0] + '.html')
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

    report_title = '{}-vs-{}'.format(os.path.splitext(json_report1)[0],
                                     os.path.splitext(json_report2)[0])
    report_filename = os.path.join(Path(json_report1).resolve().parent, report_title + '.html')
    diff_dict, gout_dict = diff_reports(json_report1, json_report2)

    print('Writing {} ...'.format(report_filename))
    with open(report_filename, 'w') as fh:
        fh.write(template.render(
            title="{}".format(report_title),
            diff_dict=diff_dict,
            gout_dict=gout_dict),
        )
    print('Done.')
