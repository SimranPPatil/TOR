import json
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import colors
from matplotlib.ticker import PercentFormatter

def get_time(jolist):
    ec = 0
    output = []
    for jo in jolist:
        if "exception" in jo:
            ec += 1
            continue
        output.append(jo["time"])
    return output, ec, float(ec/len(jolist))

def plot_histo(fe):
    hist, bins = np.histogram(fe, bins=50)
    width = 0.7 * (bins[1] - bins[0])
    center = (bins[:-1] + bins[1:]) / 2
    plt.bar(center, hist, align='center', width=width)
    plt.show()
    return


if __name__ == "__main__":
    exit_mode = True
    with open("log.log","r") as f:
        content = f.readlines()
        fixed_exit = []
        fixed_guard = []
        for line in content:
            if line[0] == "#" and "guard" in line:
                exit_mode = False
                continue
            elif line[0] == "#":
                continue

            jo = json.loads(line.strip())
            if exit_mode:
                fixed_exit.append(jo)
            else:
                fixed_guard.append(jo)

    fe, ec, portion = get_time(fixed_exit)
    print("total number of circuits tried: " + str(len(fixed_exit)))
    print("failed circuits: " + str(ec))
    print("percentage of failed circuits: " + str(portion))
    print("mean: " + str(np.mean(fe)))
    print("median: " + str(np.median(fe)))
    print("std: " + str(np.std(fe)))

    plot_histo(fe)


