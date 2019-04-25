import matplotlib.pyplot as plt
import numpy as np
import math
import json
import requests

OUTER_ATTRIBUTES = ["version", "build_revision"]
ATTRIBUTES = ["running", "country", 
"country_name", "region_name", "city_name", "latitude", "longitude", "as", "consensus_weight", 
"unverified_host_names", "last_restarted", "bandwidth_rate", "bandwidth_burst", 
"observed_bandwidth", "advertised_bandwidth", "platform", "version", "version_status", 
"consensus_weight_fraction", "guard_probability", "middle_probability", "exit_probability", "recommended_version", "measured"]
FLAGS = ['Authority', 'BadExit', 'BadDirectory', 'Exit', 'Fast', 'Guard', 'HSDir', 'Named', 'NoEdConsensus', 'Running', 'Stable', 'StaleDesc', 'Unnamed', 'V2Dir', 'Valid']
def parse_time(time_file):
    time_list = []
    with open(time_file, "r") as tf:
        line = tf.readlines()
        for l in line:
            time_list.append(float(l.split(",")[-1].strip()))
    return time_list

def parse_history(hist_file):
    fail_distribution = []
    with open(hist_file, "r") as hf:
        hist_dict = json.load(hf)
        for k,v in hist_dict.items():
            fail_distribution.append(len(v))
    return fail_distribution

def plot_line_graph(values, fig_index, title, name):
    values.sort()
    fig = plt.figure(fig_index)
    plt.title(title)
    plt.plot(values)
    plt.savefig( name+".png", bbox_inches="tight")

def filter_relay(hist_file, thresh):
    result_tuple = []
    with open(hist_file, "r") as hf:
        hist_dict = json.load(hf)
        for k,v in hist_dict.items():
            if len(v) > thresh:
                result_tuple.append((k,v))
    return sorted(result_tuple, key=lambda x: len(x[1]))

def writer_good(node):
    try:
        info = node['relays']
    except Exception as e:
        # new fix
        print(e, "\n", "node: ", node)
        return
    for info_obj in info:
        row = []
        flag_list = info_obj['flags']
        for attribute in OUTER_ATTRIBUTES:
            row.append(node[attribute])
        for attribute in ATTRIBUTES:
            try:
                row.append(str(info_obj[attribute]))
            except:
                row.append("NA")
        for flag in FLAGS:
            if flag in flag_list:
                row.append(flag)
            else:
                row.append("NA")
        return row

def getRelayInfo(fingerprint):
    url = "https://onionoo.torproject.org/details?search=" + fingerprint
    try:
        r = requests.get(url)
        return json.loads(r.text)
    except Exception as e:
        return {"exception": str(e)}

def fetch_infos(filtered_tuples):
    infos = {}
    for t in filtered_tuples:
        infos[t[0]] = getRelayInfo(t[0])
    return infos

if __name__ == "__main__":
    tl = parse_time("exctime_2hop.csv")
    plot_line_graph(tl, 0, "Time Until Failure", "ttf")

    hl_ge = parse_history("bad_guardexit_freq.json")
    plot_line_graph(hl_ge, 1, "Failure Frequency Distribution per GuardExit Relay", "hge")

    hl_m = parse_history("bad_middle_freq.json")
    plot_line_graph(hl_m, 2, "Failure Frequency Distribution per Middle Relay", "hm")

    filtered_m = filter_relay("bad_middle_freq.json", 5)
    filtered_ge = filter_relay("bad_guardexit_freq.json", 5)

    filtered_infos_ge = fetch_infos(filtered_ge)
    filtered_infos_m = fetch_infos(filtered_m)
    for t in filtered_ge:
        key = t[0]
        print("%s: failure count %d"%(filtered_infos_ge[key],len(t[1])))



