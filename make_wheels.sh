#!/usr/bin/env bash

set -eux

# NOTE: as the wheel is built with a GUI, it may try to steal focus, so we use the same trick as the CI
# locally, you can do:
# sudo apt-get install xvfb
# sudo /usr/bin/Xvfb $DISPLAY -screen 0 1600x1200x24 -noreset -nolock -shmem &
export DISPLAY=":0"

# list of models that fail
MODELS_TO_RUN='3264 9848 9853 18502 114735 138321 9852 112086 9849 116491 230888 5426 18742 113732 10360 266578 9851'

# change to liking
commit=master

# Python version
python_version_major="3"
python_version_minor="10"

# where the wheel will be copied from the container to the host
# probably best to avoid current dir as it's cleaned-up by git
wheel_dir="$(mktemp -d)"

# uninstall all possible NEURON versions (including the one we just installed)
remove_neuron_wheels() {
    python -m pip uninstall -y neuron neuron-nightly neuron${commit}
}

# clean-up current dir so we don't have anything cached (except the model zip files + metadata)
clean_dir() {
    git clean -xdf -e cache -e modeldb/modeldb-meta.yaml -e nrn_modeldb_ci.egg-info/ .
}


# Dockerfile we use to build NEURON wheels
contents="FROM neuronsimulator/neuron_wheel:latest-x86_64
WORKDIR /root
RUN git clone https://github.com/neuronsimulator/nrn
WORKDIR /root/nrn
RUN git checkout ${commit}
ENV NEURON_NIGHTLY_TAG='${commit}'
ENV NRN_NIGHTLY_UPLOAD=false
ENV NRN_RELEASE_UPLOAD=true
ENV SETUPTOOLS_SCM_PRETEND_VERSION=9.0.0
ENV NRN_BUILD_FOR_UPLOAD=1
ENV NRN_PARALLEL_BUILDS=24
RUN packaging/python/build_wheels.bash linux ${python_version_major}${python_version_minor} coreneuron"

# build the wheel (completely fresh, inside of container)
echo "${contents}" | docker build -t neuron-container --no-cache -

# need to copy wheel dir back to the host
docker create --name dummy neuron-container
docker cp dummy:/root/nrn/wheelhouse/ "${wheel_dir}"
docker rm -f dummy


# install modeldb CI scripts
python -m pip install -e .

# remove any leftover wheels
remove_neuron_wheels

# stable (reference) version
python -m pip install --force-reinstall --no-cache-dir 'neuron==8.2.6'

# before running, remove any cached wheels
clean_dir

# run with version that works
runmodels --clean --gout --workdir=stable $MODELS_TO_RUN

# before running again, remove any wheels
remove_neuron_wheels

# install the wheel
python -m pip install --no-cache-dir --force-reinstall "${wheel_dir}/wheelhouse"/*${commit}*cp${python_version_major}${python_version_minor}*.whl

# run with version that doesn't work
runmodels --clean --gout --workdir=unstable $MODELS_TO_RUN

# cleanup wheels again
remove_neuron_wheels

# report diff
diffreports2html stable.json unstable.json
