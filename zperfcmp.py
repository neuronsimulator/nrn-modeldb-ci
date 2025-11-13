# python -i zperfcmp.py 8.2 master
# Requires nrn branch hines/8.2-runtime and/or hines/master-runtime
# Plots linear and log-log  accumulated fadvance, pc.psolve, cvode.solve
# runtimes.

import json
import sys

xaxis = sys.argv[-2]
yaxis = sys.argv[-1]


def rd(jsfile):
    f = open(jsfile, "r")
    js = json.load(f)
    data = {}
    for id in js:
        if "nrn_run" in js[id]:
            lines = js[id]["nrn_run"]
            for line in lines:
                if "ZZZZ" in line:
                    x = line.split()
                    try:
                        if x[-2] == "runtime":
                            data[id] = float(x[-1][:-1])  # eliminate trailing"
                    except:
                        pass
    return data


j8 = rd(xaxis + ".json")
master = rd(yaxis + ".json")

combine = []
for id in j8:
    if id in master:
        combine.append([id, j8[id], master[id]])

combine.sort(key=lambda x: x[1])


def f(x, logar):
    return h.log10(x) if logar else x


from neuron import h, gui


def grph(logar):
    g = h.Graph()
    g.beginline(2, 1)
    for x in [0.001, 0.01, 0.1, 1.0, 10.0, 100.0]:
        g.line(f(x, logar), f(x, logar))
    g.flush()
    for i in combine:
        g.mark(f(i[1], logar), f(i[2], logar), "O", 6, 1, 1)
    g.exec_menu("View = plot")
    xlab = "log10(%s time)" % (xaxis,) if logar else "%s time(s)" % (xaxis,)
    ylab = "log10(%s time)" % (yaxis,) if logar else "%s time(s)" % (yaxis,)
    g.label(f(0.001, logar), f(100.0, logar), ylab, 1, 1, 0, 0, 1)
    g.label(f(100.0, logar), f(0.001, logar), xlab, 1, 1, 1, 0, 1)
    return g


print(f"Number of runtimes {len(combine)}")
for i, name in enumerate([xaxis, yaxis]):
    print(f"total runtime for {name} : {sum([x[i + 1] for x in combine])}")

z = [grph(0), grph(1)]
