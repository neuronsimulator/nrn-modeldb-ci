import numpy as np
import json
import re
import difflib
import logging
import os
import subprocess
from .modeldb import ModelDB
from pygments import highlight
from pygments.lexers import DiffLexer
from pygments.formatters import HtmlFormatter


mdb = ModelDB()

def curate_run_data(run_data, model=None):
    curated_data = run_data

    regex_dict = {
        # /../nrniv: Assignment to modern physical constant FARADAY	<-> ./x86_64/special: Assignment to modern physical constant FARADAY
        "^/.*?/nrniv:": "%neuron-executable%:",
        "^\\./x86_64/special:": "%neuron-executable%:",
        # nrniv: unable to open font "*helvetica-medium-r-normal*--14*", using "fixed" <-> special: unableto open font "*helvetica-medium-r-normal*--14*", using "fixed"
        "^nrniv:": "%neuron-executable%:",
        "^special:": "%neuron-executable%:",
        "(Mon|Tue|Wed|Thu|Fri|Sat|Sun) (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) \d+ \d+:\d+:\d+ [A-Z]+ \d+": "%date_command%",
        "total run time [0-9\.]+": "total run time %run_time%",
        "(^.*distutils.*$)": "",
    }

    for model_specific_substitution in mdb.run_instr.get(model, {}).get("curate_patterns", []):
        regex_dict[model_specific_substitution["pattern"]] = model_specific_substitution["repl"]

    for regex_key, regex_value in regex_dict.items():
        updated_data = []
        for line in curated_data:
            new_line, number_of_subs = re.subn(regex_key, regex_value, line)
            if number_of_subs:
                logging.debug("{} matched {} time(s)".format(regex_key, number_of_subs))
                logging.debug("{} -> {}".format(line, new_line))
            # if we are replacing a full line with an empty string, don't add it to the curated data
            if new_line:
                updated_data.append(new_line)
        curated_data = updated_data

    return curated_data


def diff_reports(report1_json, report2_json):
    diff_dict = {}
    gout_dict = {}
    runtime_dict = {}

    with open(report1_json, 'r+') as f, open(report2_json, 'r+') as f2:
        data_a = json.load(f)
        data_b = json.load(f2)

        hd = difflib.HtmlDiff()
        diff_dict["0"] = hd.make_table(json.dumps(data_a["0"], indent='\t').split('\n'),
                                             json.dumps(data_b["0"], indent='\t').split('\n')).replace("\n", "")
        for k in data_a.keys():
            if int(k) == 0:
                continue  # skip info key

            curated_a = curate_run_data(data_a[k]["nrn_run"], model=int(k))
            curated_b = curate_run_data(data_b[k]["nrn_run"], model=int(k))
            if curated_a != curated_b:
                ud = difflib.unified_diff(curated_a, curated_b,  fromfile=data_a[k]["run_info"]["start_dir"],
                                             tofile=data_b[k]["run_info"]["start_dir"])
                diff_dict[k] = highlight('\n'.join(ud), DiffLexer(), HtmlFormatter(linenos=True, cssclass="colorful", full=True))
                
            def _speedup(a, b):
                dict = {}
                dict["v1"] = a
                dict["v2"] = b
                # compute slowdown/speedup relative to runtime_b (negative means slowdown)
                dict["speedup"] = (float(b) - float(a)) / float(b) * 100
                return dict

            # List of keys that make gout comparison and speedup comparison pointless
            skip_keys = {"do_not_run", "moderr", "nrn_run_err"}
            if skip_keys.isdisjoint(data_a[k]) and skip_keys.isdisjoint(data_b[k]):
                # compare runtimes and compute slowdown or speedup
                runtime_dict[k] = {}
                runtime_dict[k]["total"] = _speedup(data_a[k]["run_time"], data_b[k]["run_time"])
                for runkey in ("model", "nrnivmodl"):
                    if runkey in data_a[k]["run_times"] and runkey in data_b[k]["run_times"]:
                        runtime_dict[k][runkey] = _speedup(data_a[k]["run_times"][runkey], data_b[k]["run_times"][runkey])
                
                # compare gout
                gout_a_file = os.path.join(data_a[k]["run_info"]["start_dir"], "gout")
                gout_b_file = os.path.join(data_b[k]["run_info"]["start_dir"], "gout")
                # gout may be missing in one of the paths. `diff -N` treats non-existent files as empty.
                if os.path.isfile(gout_a_file) or os.path.isfile(gout_b_file):
                    diff_out = subprocess.getoutput("diff -uN {} {} | head -n 30".format(gout_a_file, gout_b_file))
                    if diff_out:
                        gout_dict[k] = highlight(diff_out, DiffLexer(), HtmlFormatter(linenos=True, cssclass="colorful", full=True))

    return diff_dict, gout_dict, runtime_dict


