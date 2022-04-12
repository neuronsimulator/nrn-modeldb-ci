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
            updated_data.append(new_line)
        curated_data = updated_data

    return curated_data


def diff_reports(report1_json, report2_json):
    diff_dict = {}
    gout_dict = {}

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
                diff_dict[k] = hd.make_table(curated_a, curated_b,
                                             fromdesc=data_a[k]["run_info"]["start_dir"],
                                             todesc=data_b[k]["run_info"]["start_dir"],
                                             context=True).replace("\n", " ")

            # List of keys that make gout comparison pointless
            skip_gout_keys = {"do_not_run", "moderr", "nrn_run_err"}
            if skip_gout_keys.isdisjoint(data_a[k]) and skip_gout_keys.isdisjoint(data_b[k]):
                gout_a_file = os.path.join(data_a[k]["run_info"]["start_dir"], "gout")
                gout_b_file = os.path.join(data_b[k]["run_info"]["start_dir"], "gout")

                # gout may be missing in one of the paths. `diff -N` treats non-existent files as empty.
                if os.path.isfile(gout_a_file) or os.path.isfile(gout_b_file):
                    diff_out = subprocess.getoutput("diff -uN {} {} | head -n 30".format(gout_a_file, gout_b_file))
                    if diff_out:
                        gout_dict[k] = highlight(diff_out, DiffLexer(), HtmlFormatter(linenos=True, cssclass="colorful", full=True))

    return diff_dict, gout_dict


if __name__ == "__main__":
    d1, d2 = diff_reports('802.json', 'nightly.json')
    with open("output.html", 'w') as outhdl:
        for k, v in d1.items():
            outhdl.write(str(k))
            outhdl.write('<pre>{}</pre>'.format(str(v)))
    with open("output-gout.html", 'w') as outhdl:
        for k, v in d2.items():
            outhdl.write(str(k))
            outhdl.write('<pre>{}</pre>'.format(str(v)))

