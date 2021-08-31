# nrn-modeldb-ci

## Installation

In your virtual environment, install in editable mode: 

```
pip install -e .
```

NOTE: You have to install NEURON by yourself (wheel, CMake install).

## Usage

The following commands are now available:

* `getmodels` -> retrieve all or specified models from ModelDB.
  ```
  getmodels -h
  ```
  
* `runmodels` -> run `nrn-modeldb-ci` for all or specified models.
  ```
  runmodels -h
  ```
  Note that models have to be downloaded beforehand with `getmodels`.
  
* `modeldb-config` -> list configuration for `nrn-modeldb-ci`:
  ```
    modeldb-config
  ```
    
  | Config                  | Details                                                                     |
  | ---                     | ----                                                                        |
  | ROOT_DIR                | location of `nrn-modeldb-ci` installation                                   |
  | MODELDB_ROOT_DIR        | path to `modeldb` package inside `nrn-modeldb-ci`                           |
  | MODELDB_RUN_FILE        | yaml file containing run instructions for models (required for `runmodels`) |
  | MODELDB_METADATA_FILE   | yaml file containing model info for those downloaded with `getmodels`       |
  | MODELS_ZIP_DIR          | location of cache folder for models populated via `getmodels`               |
  | MDB_NEURON_MODELS_URL   | url used to get list of all NEURON model ids (necessary for `getmodels`)    |
  | MDB_MODEL_DOWNLOAD_URL  | url template used for model downloading (cf `{model_id}`)                   |

## Model Run

### MODELDB_RUN_FILE 

This is where the "black magic" lives, instructions on how to run models from ModelDB. 
Default handling is available in case there are no entries for a given model id. 

All entries are optional:

| yaml entry | special value   | Details                                                       | Default handling       |
| ---        | ---             | ----                                                          | ---                    |
| run        |                 | custom instructions used to effectively run the model         | `verify_graph_()`     *|
| run        | null            | `DoNotRun` mode -> model is built but not run                 ||
| model_dir  |                 | custom location of `mod` sub-directory to compile             | `*.mod` @ root level   |
| model_dir  | dir;dir         | several custom `mod` sub-directories to compile               | `*.mod` @ root level   |
| skip       |                 | model is skipped from running alltogether                     ||
| comment    |                 | comment to be included in the report for `skip` or `run: null`||
| script     |                 | bash script entries needed to adjust the model before running ||

(*) `verify_graph_()` saves all lines of all graphs to the `gout` file in the model working directory.

### TODO: Model Run Activity Diagram

### Report

The generated report following `runmodels` contains te following info:

* `gout` - (optional) graph data from the neuron execution (must be run with `runmodels --gout`)
* `logs` - logs regarding model setup, nrnivmodl, ...
* `nrn_run` - command used to run the model and its output
* `run_info` - model run information
* `run_time` - model run time

For example, by running:
```
runmodels --gout test3682 3682
```
we will generate report `test3782.json` :
```yaml
{
    "3682": {
        "gout": [
            "Graphs 1\n",
            "Graph[0]\n",
            "lines 1\n",
            "points 10001\n",
            "xvec1\n",
            "0\n",
            "0.025\n",
            ".....",            # truncated
            "-57.9912\n",
            "\n"
        ],
        "logs": [
            "",
            "",
            "/usr/bin/xcrun",
            "%model_dir%",
            "-n Mod files:",
            "-n  \"%model_dir%/hh3.mod\"",
            "-n  \"%model_dir%/rglu_score.mod\"",
            "",
            "",
            "Creating x86_64 directory for .o files.",
            "",
            "COBJS=''",
            " -> \u001b[32mCompiling\u001b[0m mod_func.c",
            "gcc -O2   -I.   -I/Users/savulesc/Library/Python/3.9/lib/python/site-packages/neuron/.data/include  -I/usr/local/Cellar/open-mpi/4.0.5/include -fPIC -c mod_func.c -o mod_func.o",
            " -> \u001b[32mNMODL\u001b[0m %model_dir%/hh3.mod",
            " -> \u001b[32mNMODL\u001b[0m %model_dir%/rglu_score.mod",
            "(cd \"%model_dir%\"; MODLUNIT=/Users/savulesc/Library/Python/3.9/lib/python/site-packages/neuron/.data/share/nrn/lib/nrnunits.lib /Users/savulesc/Library/Python/3.9/lib/python/site-packages/neuron/.data/bin/nocmodl rglu_score.mod -o \"%model_dir%/x86_64\")",
            "(cd \"%model_dir%\"; MODLUNIT=/Users/savulesc/Library/Python/3.9/lib/python/site-packages/neuron/.data/share/nrn/lib/nrnunits.lib /Users/savulesc/Library/Python/3.9/lib/python/site-packages/neuron/.data/bin/nocmodl hh3.mod -o \"%model_dir%/x86_64\")",
            "Translating rglu_score.mod into %model_dir%/x86_64/rglu_score.c",
            "Notice: VERBATIM blocks are not thread safe",
            "Translating hh3.mod into %model_dir%/x86_64/hh3.c",
            "Notice: VERBATIM blocks are not thread safe",
            "Notice: This mechanism cannot be used with CVODE",
            "Notice: Assignment to the GLOBAL variable, \"inf\", is not thread safe",
            "Notice: This mechanism cannot be used with CVODE",
            "Notice: Assignment to the GLOBAL variable, \"Rtau_AMPA\", is not thread safe",
            "Notice: Assignment to the GLOBAL variable, \"Rinf_AMPA\", is not thread safe",
            "Notice: Assignment to the GLOBAL variable, \"Rtau_NMDA\", is not thread safe",
            "Notice: Assignment to the GLOBAL variable, \"Rinf_NMDA\", is not thread safe",
            "Warning: Default 37 of PARAMETER celsius will be ignored and set by NEURON.",
            "Warning: Default -100 of PARAMETER ek will be ignored and set by NEURON.",
            "Warning: Default 40 of PARAMETER ena will be ignored and set by NEURON.",
            " -> \u001b[32mCompiling\u001b[0m hh3.c",
            "gcc -O2   -I\"%model_dir%\" -I.   -I/Users/savulesc/Library/Python/3.9/lib/python/site-packages/neuron/.data/include  -I/usr/local/Cellar/open-mpi/4.0.5/include -fPIC -c hh3.c -o hh3.o",
            " -> \u001b[32mCompiling\u001b[0m rglu_score.c",
            "gcc -O2   -I\"%model_dir%\" -I.   -I/Users/savulesc/Library/Python/3.9/lib/python/site-packages/neuron/.data/include  -I/usr/local/Cellar/open-mpi/4.0.5/include -fPIC -c rglu_score.c -o rglu_score.o",
            " => \u001b[32mLINKING\u001b[0m shared library ./libnrnmech.dylib",
            "g++ -O2 -DVERSION_INFO='7.8.2' -std=c++11 -dynamiclib -Wl,-headerpad_max_install_names -undefined dynamic_lookup -fPIC  -I /Users/savulesc/Library/Python/3.9/lib/python/site-packages/neuron/.data/include -o ./libnrnmech.dylib -Wl,-install_name,@rpath/libnrnmech.dylib \\",
            "\t  ./mod_func.o ./hh3.o ./rglu_score.o  -L/Users/savulesc/Library/Python/3.9/lib/python/site-packages/neuron/.data/lib -lnrniv -Wl,-rpath,/Users/savulesc/Library/Python/3.9/lib/python/site-packages/neuron/.data/lib    -lreadline",
            "rm -f ./.libs/libnrnmech.so ; mkdir -p ./.libs ; cp ./libnrnmech.dylib ./.libs/libnrnmech.so",
            "Successfully created x86_64/special",
            ""
        ],
        "nrn_run": [
            "RUNNING -> ./x86_64/special -nobanner  %model_dir%/mosinit.hoc %model_dir%/driver.hoc",
            "0 /Users/savulesc/Library/Python/3.9/bin/nrniv: can't open ",
            "\t0 ",
            "\t1 ",
            "\t1 ",
            "\t1 ",
            "\t1 ",
            "\t1 ",
            "\t1 ",
            "\t1 ",
            "\t1 ",
            "\t1 ",
            "\t1 ",
            "Spike at 40.5 ",
            "Spike at 81.15 ",
            "Spike at 108 ",
            "Spike at 133.65 ",
            "Spike at 180.775 ",
            "Spike at 201.3 ",
            "Total spikes: 6 ",
            "\t1 ",
            "\t1 ",
            ""
        ],
        "run_info": {
            "driver": "/Users/savulesc/Workspace/nrn-modeldb-ci/test3682/synmap/driver.hoc",
            "init": "/Users/savulesc/Workspace/nrn-modeldb-ci/test3682/synmap/mosinit.hoc",
            "model_dir": "/Users/savulesc/Workspace/nrn-modeldb-ci/test3682/synmap",
            "script": [
                "echo 'use_mcell_ran4(1)' > temp",
                "cat mosinit.hoc >> temp",
                "mv temp  mosinit.hoc"
            ],
            "start_dir": "/Users/savulesc/Workspace/nrn-modeldb-ci/test3682/synmap"
        },
        "run_time": "5.724453152"
    }
}
```