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
  You can specify `--virtual` so that NEURON GUI is run in headless mode. It requires a backend (n.r. `Xvfb`)
  

* `report2html` -> create an interactive HTML report for a given json report (obtained with `runmodels`)
  ```
  report2html -h
  ```
  Note that the generated HTML file is self-contained.


* `diffgout` -> launch `nrngui` and display the two gout files in different colors.
  ```
  diffgout -h
  ```
  This can come in handy when comparing/investigating results from binary incompatible neuron versions. 


* `diffreports2html` -> create an interactive `NEURONv1-vs-NEURONv2` HTML report 
  ```
  diffreports2html -h
  ```
  The differences that are taken into account:
  * `nrn_run` and `moderr` from the json reports -> outputs side-by-side diffs
  * `gout` -> outputs git-like diffs; **NOTE**: this walks gout paths from json report `run_info`, make sure they are present.
  
  Note that the generated HTML file is self-contained.
  

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
    "0": {...} # runmodels stats, see next section
    "3682": {
        "gout": [
            "Graphs 1\n",
            "Graph[0]\n",
            "lines 1\n",
            "points 10001\n",
            "xvec1\n",
            "0\n",
            "0.025\n",
            ".....",            # truncated (can be HUGE)
            "-57.9912\n",
            "\n"
        ],
        "logs": [
            "",
            "",
            "/usr/bin/xcrun",
            "%model_dir%",
            "Mod files: \"%model_dir%/hh3.mod\" \"%model_dir%/rglu_score.mod\"",
            "",
            "Creating x86_64 directory for .o files.",
            "",
            "COBJS=''",
            " -> \u001b[32mNMODL\u001b[0m %model_dir%/hh3.mod",
            " -> \u001b[32mCompiling\u001b[0m mod_func.cpp",
            " -> \u001b[32mNMODL\u001b[0m %model_dir%/rglu_score.mod",
            "Translating hh3.mod into %model_dir%/x86_64/hh3.c",
            "Notice: VERBATIM blocks are not thread safe",
            "Translating rglu_score.mod into %model_dir%/x86_64/rglu_score.c",
            "Notice: This mechanism cannot be used with CVODE",
            "Notice: VERBATIM blocks are not thread safe",
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
            " -> \u001b[32mCompiling\u001b[0m rglu_score.c",
            " => \u001b[32mLINKING\u001b[0m shared library ./libnrnmech.dylib",
            " => \u001b[32mLINKING\u001b[0m executable ./special LDFLAGS are:   ",
            "Successfully created x86_64/special",
            "INFO : Using neuron-nightly Package (Developer Version)",
            ""
        ],
        "nrn_run": [
            "RUNNING -> ./x86_64/special -nobanner %model_dir%/mosinit.hoc %model_dir%/driver.hoc",
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
        "run_time": "7.595794515"
    }
}
```

Every `runmodels` report will hold out run statistics in the `"0"` key: 
```yaml
    "0": {
        "NEURON version": "8.0a-743-g3871f82a",
        "Stats": {
            "Failed models": {
                "Accession numbers": [
                    20212,
                    97868,
                    144549,
                    186768,
                    244262
                ],
                "Count": 5
            },
            "Failed runs": {
                "Accession numbers": [
                    194897
                ],
                "Count": 1
            },
            "No. of models run": 659
        }
    },
```

## Funding


`nrn-modeldb-ci` is developed in a joint collaboration between the Blue Brain Project and Yale University. This work is supported by funding to the Blue Brain Project, a research center of the École polytechnique fédérale de Lausanne (EPFL), from the Swiss government’s ETH Board of the Swiss Federal Institutes of Technology, NIH grant number R01NS11613 (Yale University), the European Union Seventh Framework Program (FP7/20072013) under grant agreement n◦ 604102 (HBP) and the European Union’s Horizon 2020 Framework Programme for Research and Innovation under Specific Grant Agreement n◦ 720270 (Human Brain Project SGA1), n◦ 785907 (Human Brain Project SGA2) and n◦ 945539 (Human Brain Project SGA3).