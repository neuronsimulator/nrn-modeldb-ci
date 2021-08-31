from . import config
import logging
import multiprocessing
import base64
import os
import requests
from .progressbar import ProgressBar
import yaml
from .data import Model
from .config import *
import traceback
from pprint import pformat

def download_model(model_id):
    try:
        model_json = requests.get(MDB_MODEL_DOWNLOAD_URL.format(model_id=model_id)).json()
        model = Model(
            *(
                model_json[key]
                for key in ("object_id", "object_name", "object_created", "object_ver_date")
            )
        )
        url = None
        for att in model_json["object_attribute_values"]:
            if att["attribute_id"] == 23:
                url = att["value"]
                break
        # print(model.id)
        model_zip_uri = os.path.join(
            MODELS_ZIP_DIR, "{model_id}.zip".format(model_id=model.id)
        )
        with open(model_zip_uri, "wb+") as zipfile:
            zipfile.write(base64.standard_b64decode(url["file_content"]))
    except Exception as e:   #  noqa
        model = e

    return model_id, model


class ModelDB(object):
    metadata = property(lambda self: self._metadata)
    run_instr = property(lambda self: self._run_instr)

    def __init__(self):
        self._metadata = {}
        self._run_instr = {}

        self._load_run_instructions()
        try:
            self._load_metadata()
        except FileNotFoundError:
            logging.warning(
                "{} not found!".format(MODELDB_METADATA_FILE)
            )
        except yaml.YAMLError as y:
            logging.error("Error loading {}: {}".format(MODELDB_METADATA_FILE, y))
            raise y
        except Exception as e:
            raise e

    def _download_models(self, model_list=None):
        if not os.path.isdir(MODELS_ZIP_DIR):
            logging.info("Creating cache directory: {}".format(MODELS_ZIP_DIR))
            os.mkdir(MODELS_ZIP_DIR)
        models = requests.get(MDB_NEURON_MODELS_URL).json() if model_list is None else model_list
        pool = multiprocessing.Pool()
        processed_models = pool.imap_unordered(download_model, models)
        download_err = {}
        for model_id, model in ProgressBar.iter(processed_models, len(models)):
            if not isinstance(model, Exception):
                self._metadata[model_id] = model
            else:
                download_err[model_id] = model

        if download_err:
            logging.error("Error downloading models:")
            logging.error(pformat(download_err))

        self._save_metadata()

    def _load_metadata(self):
        with open(MODELDB_METADATA_FILE) as meta_file:
            self._metadata = yaml.load(meta_file, yaml.Loader)

    def _load_run_instructions(self):
        with open(MODELDB_RUN_FILE) as run_file:
            self._run_instr = yaml.load(run_file, yaml.Loader)

    def _save_metadata(self):
        with open(MODELDB_METADATA_FILE, "w+") as meta_file:
            yaml.dump(self._metadata, meta_file, sort_keys=True)

    def download_models(self, model_list=None):
        if model_list is None:
            try:
                os.remove(MODELDB_METADATA_FILE)
            except OSError:
                pass
        self._download_models(model_list)

    # TODO -> check/update models
    def update_models(self):
        pass

