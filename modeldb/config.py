"""Global configuration variables used in the project"""

import os

MDB_NEURON_MODELS_URL = (
    "http://modeldb.science/api/v1/models/{model_field}?modeling_application=NEURON"
)
MDB_MODEL_METADATA_URL = "https://modeldb.science/api/v1/models/{model_id}"
MDB_MODEL_DOWNLOAD_URL = "https://modeldb.science/eavBinDown?o={model_id}"

ROOT_DIR = os.path.abspath(__file__ + "/../../")

MODELS_ZIP_DIR = "%s/cache" % ROOT_DIR
MODELDB_ROOT_DIR = "%s/modeldb" % ROOT_DIR
MODELDB_METADATA_FILE = "%s/modeldb-meta.yaml" % MODELDB_ROOT_DIR
MODELDB_RUN_FILE = "%s/modeldb-run.yaml" % MODELDB_ROOT_DIR
