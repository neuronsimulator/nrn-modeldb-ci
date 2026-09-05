# python -i perfcmp1.py 8.2 master
# Plots linear and log-log nrniv runtimes.

import sys

xaxis = sys.argv[-2]
yaxis = sys.argv[-1]


def rd(logfile):
    f = open(logfile, "r")
    lines = f.readlines()
    data = {}
    for line in lines:
        if "Done for:" in line:
            x = line.split()
            try:
                x = [x[i] for i in [7, 10, 12]]
                x = [x[0], float(x[1][:-1]), float(x[2][:-1])]
                data[x[0]] = x[1:]
            except:
                pass
    return data


j8 = rd(xaxis + ".log")
master = rd(yaxis + ".log")

combine = []
for id in j8:
    if id in master:
        combine.append([id, j8[id][1], master[id][1]])

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


print(f"Number of runmodel {len(j8.values())}")
dat = [j8, master]
for d, name in enumerate([xaxis, yaxis]):
    for istyle, style in enumerate(["nrnivmodl", "nrniv"]):
        print(f"total {style} for {name} : {sum([x[istyle] for x in dat[d].values()])}")

z = [grph(0), grph(1)]
