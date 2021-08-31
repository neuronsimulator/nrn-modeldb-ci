import logging
from docopt import docopt
from os.path import abspath
from pprint import pprint
from . import config
from .modelrun import ModelRunManager
from .modeldb import ModelDB
import inspect

def runmodels(args=None):
    """runmodels

    Run nrn-modeldb-ci for all or specified models

    Usage:
        runmodels <WorkingDirectory> [options] [<model_id>...]
        runmodels -h    Print help

    Arguments:
        WorkingDirectory=PATH   Required: directory where to run the models and store the reports
        model_id=<n>            Optional: ModelDB accession number(s) to run; default is all available models

    Options:
        --gout                  Include gout into the report. Note that gout data can be very big, so disabled by default.

    Examples
        runmodels /path/to/workdir
        runmodels /path/to/workdir 23613 12344
    """
    options = docopt(runmodels.__doc__, args)
    working_dir = options.pop("<WorkingDirectory>")
    model_ids = [int(model_id) for model_id in options.pop("<model_id>")]
    gout = options.pop("--gout", False)

    ModelRunManager(working_dir, gout=gout).run_models(model_list=model_ids if model_ids else None)


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


def modeldb_config(args=None):
    cfg_module = globals().get('config', None)
    pprint({var: getattr(cfg_module, var) for var in dir(cfg_module) if
            not inspect.ismodule(var) and not var.startswith("__") and not var.endswith("__")})
