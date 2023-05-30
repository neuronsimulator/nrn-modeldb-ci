"""Global configuration variables used in the project"""

import os

ROOT_DIR = os.path.abspath(__file__ + "/../../")

MODELS_ZIP_DIR = "%s/cache" % ROOT_DIR
MODELDB_ROOT_DIR = "%s/modeldb" % ROOT_DIR
MODELDB_METADATA_FILE = "%s/modeldb-meta.yaml" % MODELDB_ROOT_DIR
MODELDB_RUN_FILE = "%s/modeldb-run.yaml" % MODELDB_ROOT_DIR