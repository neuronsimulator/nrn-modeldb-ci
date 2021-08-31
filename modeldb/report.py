import pandas as pd
import numpy as np
import json
from pprint import pprint


def diff_reports(report1_json, report2_json):
    with open(report1_json, 'r+') as f:
        data_a = json.load(f)
        with open(report2_json, 'r+') as f2:
            data_b = json.load(f2)
            import difflib
            import webbrowser

            with open('output.html', 'w') as fh:
                d = difflib.HtmlDiff()  # wrapcolumn=10)
                for k in data_a.keys():
                    if data_a[k]["nrn_run"] != data_b[k]["nrn_run"]:
                        html = d.make_file(data_a[k]["nrn_run"], data_b[k]["nrn_run"])
                        # save in file
                        fh.write(k)
                        fh.write(html)

            # open in web browser
            webbrowser.open('output.html')


if __name__ == "__main__":
    diff_reports('test.json', 'test2.json')