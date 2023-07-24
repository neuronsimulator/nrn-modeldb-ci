from .config import *
from .data import Model
import logging
import multiprocessing
import os
from pprint import pformat
from .progressbar import ProgressBar
import requests
import time
import yaml


def download_model(arg_tuple):
    model_id, model_run_info, expected_ver_date = arg_tuple
    try:
        # Fetch the model metadata from ModelDB.
        model_json = requests.get(
            MDB_MODEL_METADATA_URL.format(model_id=model_id)
        ).json()
        # Check that the timestamp matches our expectations.
        assert model_json["ver_date"] == expected_ver_date
        # Assemble a Model object from the JSON metadata just fetched
        # and store model_id in the id field for easy retrieval of correct zip file
        model = Model(
            model_id,
            model_json["name"],
            model_json["created"],
            model_json["ver_date"],
        )
        # Now fetch the actual model data .zip file. By default this also comes
        # from ModelDB, but it can be overriden to come from GitHub instead.
        if "github" in model_run_info:
            # This means we should try to download the model content from
            # GitHub instead of from ModelDB.
            github = model_run_info["github"]
            organisation = "ModelDBRepository"
            suffix = ""  # default branch
            if github == "default":
                # Using
                #   github: "default"
                # in modeldb-run.yaml implies that we fetch the HEAD of the
                # default branch from ModelDBRepository on GitHub. In general
                # this should be the same thing as fetching from ModelDB.
                pass
            elif github.startswith("pull/"):
                # Using
                #   github: "pull/4"
                # in modeldb-run.yaml implies that we use the branch from pull
                # request #4 to ModelDBRepository/{model_id} on GitHub. This is
                # used if you want to test updates to models.
                pr_number = int(github[5:])
                suffix = "/pull/{}/head".format(pr_number)
            elif github.startswith("/"):
                # Using
                #   github: "/myname"
                # in modeldb-run.yaml implies that we fetch the HEAD of the
                # default branch of myname/{model_id} on GitHub. This is useful
                # if you need to test changes to a model that does not exist on
                # GitHub under the ModelDBRepository organisation.
                organisation = github[1:]
            else:
                raise Exception("Invalid value for github key: {}".format(github))
            url = "https://api.github.com/repos/{organisation}/{model_id}/zipball{suffix}".format(
                model_id=model_id, organisation=organisation, suffix=suffix
            )
        else:
            # Get the .zip file from ModelDB, not from GitHub.
            url = MDB_MODEL_DOWNLOAD_URL.format(model_id=model_id)

        # Construct the path we want to save the .zip at locally.
        model_zip_uri = os.path.join(
            MODELS_ZIP_DIR, "{model_id}.zip".format(model_id=model_id)
        )  # note model_id may not be same as model.id

        # Download the model data from `url`. Retry a few times on failure.
        num_attempts = 3
        status_codes = []
        for _ in range(num_attempts):
            model_download_response = requests.get(url)
            status_codes.append(model_download_response.status_code)
            if model_download_response.status_code == requests.codes.ok:
                break
            time.sleep(5)
        else:
            raise Exception(
                "Failed to download {} with status codes {}".format(url, status_codes)
            )
        with open(model_zip_uri, "wb+") as zipfile:
            zipfile.write(model_download_response.content)
    except Exception as e:  #  noqa
        model = e

    return model_id, model


class ModelDB(object):
    logger = None
    metadata = property(lambda self: self._metadata)
    run_instr = property(lambda self: self._run_instr)

    def __init__(self):
        self._metadata = {}
        self._run_instr = {}

        self._load_run_instructions()
        self._setup_logging()
        try:
            self._load_metadata()
        except FileNotFoundError:
            ModelDB.logger.warning("{} not found!".format(MODELDB_METADATA_FILE))
        except yaml.YAMLError as y:
            ModelDB.logger.error(
                "Error loading {}: {}".format(MODELDB_METADATA_FILE, y)
            )
            raise y
        except Exception as e:
            raise e

    def download_models(self, model_list=None):
        if not os.path.isdir(MODELS_ZIP_DIR):
            ModelDB.logger.info("Creating cache directory: {}".format(MODELS_ZIP_DIR))
            os.mkdir(MODELS_ZIP_DIR)

        # Fetch the list of NEURON model IDs, and a list of timestamps for
        # those models. We do this even if `model_list` is not None to build
        # the model ID -> timestamp mapping.
        def query(field):
            return requests.get(MDB_NEURON_MODELS_URL.format(model_field=field)).json()

        all_model_ids = query("id")

        # The above are model entries (conceptual models) that have NEURON
        # implementations. But a few of those id are not associated with downloading
        # the NEURON zip file by default. So examine those entry id that
        # have multiple "modeling_application" and if there is an
        # "alternative_version" with "object_name" containing "NEURON",
        # add those id to the all_model_ids list and remove the id that
        # are not associated with NEURON zip file download
        # For example, replace 45539 traub ifc fortran with
        # 113435 traub NEURON and 116860 traub NEURON 7
        # and a bunch of Allen models with Standalone NEURON versions.
        # Also prepare a parallel list of the version dates.
        def adjust_for_nrnzip(nrnids):
            # There may be multiple additions that replace one removal
            new_nrnids = []
            new_verdates = []  # keep parallel with new_nrnids

            # next three are parallel to nrnids
            alts = query("alternative_version")
            apps = query("modeling_application")
            verdates = query("ver_date")

            for i, id in enumerate(nrnids):
                changed = False
                if len(apps[i]["value"]) > 1:
                    if alts[i]:
                        for sim in alts[i]["value"]:
                            if "NEURON" in sim["object_name"]:
                                nrnid = sim["object_id"]
                                if nrnid != nrnids[i]:
                                    new_nrnids.append(nrnid)
                                    new_verdates.append(verdates[i])
                                    changed = True
                if not changed:
                    new_nrnids.append(id)
                    new_verdates.append(verdates[i])
            return new_nrnids, new_verdates

        all_model_ids, all_model_timestamps = adjust_for_nrnzip(all_model_ids)

        metadata = {
            model_id: timestamp
            for model_id, timestamp in zip(all_model_ids, all_model_timestamps)
        }
        # If we were passed a non-None `model_list`, restrict those models now.
        if model_list is not None:
            missing_ids = set(model_list) - set(metadata.keys())
            if missing_ids:
                raise Exception(
                    "Model IDs {} were explicitly requested, but are not known NEURON models.".format(
                        missing_ids
                    )
                )
            metadata = {model_id: metadata[model_id] for model_id in model_list}
        # For each model in `metadata`, check if a cached entry exists and is
        # up to date. If not, download it.
        models_to_download = []
        for model_id, new_ver_date in metadata.items():
            if model_id in self._metadata and os.path.exists(
                os.path.join(MODELS_ZIP_DIR, "{model_id}.zip".format(model_id=model_id))
            ):
                cached_ver_date = self._metadata[model_id]._ver_date
                if cached_ver_date == new_ver_date:
                    ModelDB.logger.debug(
                        "Model {} cache up to date ({})".format(model_id, new_ver_date)
                    )
                    continue
                else:
                    ModelDB.logger.debug(
                        "Model {} cache out of date (cached: {}, new: {})".format(
                            model_id, cached_ver_date, new_ver_date
                        )
                    )
            else:
                ModelDB.logger.debug("Model {} not found in cache".format(model_id))
            models_to_download.append(
                (model_id, self._run_instr.get(model_id, {}), new_ver_date)
            )
        # Download the missing or out of date models in parallel
        pool = multiprocessing.Pool(8)
        processed_models = pool.imap_unordered(download_model, models_to_download)
        download_err = {}
        for model_id, model in ProgressBar.iter(
            processed_models, len(models_to_download)
        ):
            if not isinstance(model, Exception):
                self._metadata[model_id] = model
            else:
                download_err[model_id] = model

        if download_err:
            ModelDB.logger.error("Error downloading models:")
            ModelDB.logger.error(pformat(download_err))

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

    def _setup_logging(self):
        if ModelDB.logger is not None:
            return
        formatter = logging.Formatter(
            fmt="%(asctime)s :: %(levelname)-8s :: %(message)s"
        )
        consoleHandler = logging.StreamHandler()
        consoleHandler.setFormatter(formatter)
        consoleHandler.setLevel(logging.INFO)
        fileHandler = logging.FileHandler("modeldb.log")
        fileHandler.setFormatter(formatter)
        fileHandler.setLevel(logging.DEBUG)
        ModelDB.logger = logging.getLogger("modeldb")
        ModelDB.logger.setLevel(logging.DEBUG)
        ModelDB.logger.addHandler(consoleHandler)
        ModelDB.logger.addHandler(fileHandler)
