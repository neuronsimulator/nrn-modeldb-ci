from . import config
import logging
import multiprocessing
import base64
import os
import requests
import time
from .progressbar import ProgressBar
import yaml
from .config import *
import traceback
from pprint import pformat


def download_model(arg_tuple):
    model_id, model_run_info = arg_tuple
    try:
        model_zip_uri = os.path.join(
            MODELS_ZIP_DIR, "{model_id}.zip".format(model_id=model_id))

        suffix = model_run_info["github"] if "github" in model_run_info else "master"
        github_url = "https://github.com/ModelDBRepository/{model_id}/archive/refs/heads/{suffix}.zip".format(
            model_id=model_id, suffix=suffix
        )
      
        # download github_url to model_zip_uri
        logging.info("Downloading model {} from {}".format(model_id, github_url))
        response = requests.get(github_url, stream=True)
        if response.status_code != 200:
            raise Exception("Failed to download model: {}".format(response.text))
        with open(model_zip_uri, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)
                    f.flush()
        logging.info("Downloaded model {} to {}".format(model_id, model_zip_uri))
    except Exception as e:  #  noqa
        github_url = e

    return model_id, github_url


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

    def _gh_cli_get_neuron_simulator_repositories(self):
        import subprocess

        # Run the gh command to fetch the repository list and capture the output
        command = ['gh', 'repo', 'list', 'modeldbrepository', '--topic', 'neuron-simulator', '--json', 'name', '-L', '2000']
        output = subprocess.check_output(command, text=True)

        # Parse the json output to get the repository names
        import json
        repositories = json.loads(output)
        return [int(repository['name']) for repository in repositories]
        
    def _download_models(self, model_list=None):
        if not os.path.isdir(MODELS_ZIP_DIR):
            logging.info("Creating cache directory: {}".format(MODELS_ZIP_DIR))
            os.mkdir(MODELS_ZIP_DIR)
        models = self._gh_cli_get_neuron_simulator_repositories() if model_list is None else model_list
        pool = multiprocessing.Pool()
        processed_models = pool.imap_unordered(
            download_model,
            [(model_id, self._run_instr.get(model_id, {})) for model_id in models],
        )
        download_err = {}
        for model_id, model_url in ProgressBar.iter(processed_models, len(models)):
            
            if not isinstance(model_url, Exception):
                model_meta = {}
                model_meta["id"] = model_id
                model_meta["url"] = model_url   
                self._metadata[model_id] = model_meta
            else:
                download_err[model_id] = model_url

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

