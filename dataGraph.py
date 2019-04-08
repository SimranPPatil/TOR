import matplotlib.pyplot as plt
import numpy as np
import math




def generateGraph(reformatted_list, real_features, categorical_features):
    i = 0
    for fe in real_features:
        i+=1
        label_dict = {}
        min_max = []
        for r in reformatted_list:
            l = r["label"]

            if fe not in r:
                continue

            if l not in label_dict:
                label_dict[l] = []
            label_dict[l].append(r[fe])
            min_max.append(r[fe])
        mi = math.floor(min(min_max))
        ma = math.ceil(max(min_max))
        bins = np.linspace(mi, ma, 100)
        realValueGraph(fe, label_dict, i, bins)

    exit()

    for fe in categorical_features:
        i+= 1
        label_dict = {}
        value = set()
        label = set()
        for r in reformatted_list:
            l = r["label"]
            label.add(l)

            if fe not in r:
                continue
            v = r[fe]
            value.add(v)

            if l not in label_dict:
                label_dict[l] = {}
            if v not in label_dict[l]:
                label_dict[l][v] = 0
            label_dict[l][v] += 1
        value = list(value)
        if len(value) > 100:
            continue
        label = list(label)
        catValueGraph(fe, label_dict, i, label, value)

        
def catValueGraph(feature, label_dict, i, label_order, value_order):
    fig = plt.figure(i)
    plt.title(feature)
    bar_width = 0.1
    index = np.arange(len(label_order))
    offset = 0
    for a in value_order:
        vec = []
        for l in label_order:
            if l not in label_dict:
                continue
            v = label_dict[l]
            if a not in v:
                vec.append(0)
            else:
                vec.append(v[a])
        plt.bar(index + offset*bar_width, vec, bar_width, label=a)
        offset += 1
    plt.legend(bbox_to_anchor=(1.04,0.5), loc="center left", borderaxespad=0)
    plt.savefig( feature + ".png", bbox_inches="tight")

def realValueGraph(feature, label_dict, i, bins):
    fig = plt.figure(i)
    plt.title(feature)
    for k, v in label_dict.items():
        plt.hist(v, bins = 100, alpha=0.3, label=k)
    plt.legend(bbox_to_anchor=(1.04,0.5), loc="center left", borderaxespad=0)
    plt.savefig( feature + ".png", bbox_inches="tight")
