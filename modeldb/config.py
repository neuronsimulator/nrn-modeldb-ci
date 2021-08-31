"""Global configuration variables used in the project"""

import os

# MDB_NEURON_MODELS_URL = "https://senselab.med.yale.edu/_site/webapi/object.json/?cl=19&oid=1882"
MDB_NEURON_MODELS_URL = (
    "http://modeldb.science/api/v1/models?modeling_application=NEURON"
)
MDB_MODEL_DOWNLOAD_URL = (
    "https://senselab.med.yale.edu/_site/webapi/object.json/{model_id}"
)

ROOT_DIR = os.path.abspath(__file__ + "/../../")

MODELS_ZIP_DIR = "%s/cache" % ROOT_DIR
MODELDB_ROOT_DIR = "%s/modeldb" % ROOT_DIR
MODELDB_METADATA_FILE = "%s/modeldb-meta.yaml" % MODELDB_ROOT_DIR
MODELDB_RUN_FILE = "%s/modeldb-run.yaml" % MODELDB_ROOT_DIR