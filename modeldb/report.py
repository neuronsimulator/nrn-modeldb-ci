import numpy as np
import json
import re
import difflib
import os
import subprocess
from collections import defaultdict


def curate_run_data(run_data):
    curated_data = run_data

    regex_dict = {
        # /../nrniv: Assignment to modern physical constant FARADAY	<-> ./x86_64/special: Assignment to modern physical constant FARADAY
        "^/.*?/nrniv:": "",
        "^\\./x86_64/special:": "",
    }

    for regex_key, regex_value in regex_dict.items():
        curated_data = [re.sub(regex_key, regex_value, line) for line in curated_data]

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
            curated_a = curate_run_data(data_a[k]["nrn_run"])
            curated_b = curate_run_data(data_b[k]["nrn_run"])
            if curated_a != curated_b:
                diff_dict[k] = hd.make_table(curated_a, curated_b, context=True).replace("\n", " ")
            if "do_not_run" not in data_a[k]:
                gout_a_file = os.path.join(data_a[k]["run_info"]["start_dir"], "gout")
                gout_b_file = os.path.join(data_b[k]["run_info"]["start_dir"], "gout")

                # gout may be missing in one of the paths. `diff -N` treats non-existent files as empty.
                if os.path.isfile(gout_a_file) or os.path.isfile(gout_b_file):
                    gout_dict[k] = subprocess.getoutput("diff -uN {} {} | head -n 30 |  pygmentize -l diff -f html -O full,style=colorful,linenos=1".format(gout_a_file, gout_b_file,k))

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

