set -eux
MODELS_TO_RUN='3264 9848 9853 18502 114735 138321 9852 112086 9849 116491 230888 5426 18742 113732 10360 266578 9851'

git clean -df .

python -m pip install -e /home/jelic/software/nrn-modeldb-ci

python -m pip uninstall -y neuron neuron-nightly

python -m pip install 'neuron==8.2.6'

nrn_ver1="$(python -c "from neuron import __version__ as nrn_ver; print(nrn_ver)")"
runmodels --clean --gout --workdir=$nrn_ver1 $MODELS_TO_RUN

python -m pip uninstall -y neuron neuron-nightly

python -m pip install /home/jelic/software/nrn/wheelhouse/*cp${minor_version}*.whl

nrn_ver2="$(python -c "from neuron import __version__ as nrn_ver; print(nrn_ver)")"
runmodels --clean --gout --workdir=$nrn_ver2 $MODELS_TO_RUN

diffreports2html ${nrn_ver1}.json ${nrn_ver2}.json
