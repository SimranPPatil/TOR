import glob
import json
import csv
import re, sys
from datetime import datetime

OUTER_ATTRIBUTES = ["version", "build_revision"]
ATTRIBUTES = ["running", "country", 
"country_name", "region_name", "city_name", "latitude", "longitude", "as", "consensus_weight", 
"unverified_host_names", "last_restarted", "bandwidth_rate", "bandwidth_burst", 
"observed_bandwidth", "advertised_bandwidth", "platform", "version", "version_status", 
"consensus_weight_fraction", "guard_probability", "middle_probability", "exit_probability", "recommended_version", "measured"]
FLAGS = ['Authority', 'BadExit', 'BadDirectory', 'Exit', 'Fast', 'Guard', 'HSDir', 'Named', 'NoEdConsensus', 'Running', 'Stable', 'StaleDesc', 'Unnamed', 'V2Dir', 'Valid']

LOGFILE = []
with open('failures3.log') as logfile:
    for line in logfile:
        LOGFILE.append(line)

EPOCHS = {}
historic_bad = {}
FL = 0

for filename in glob.glob('./DC/MiddleRelayProfile*.json'):
        try:
            run_date = filename.split('MiddleRelayProfile')[1].split(' ')[0]
            run_time = filename.split('MiddleRelayProfile')[1].split(' ')[1].split('.')[0]
            EPOCHS.setdefault(run_date, []).append(run_time)
        except:
            continue

for key in EPOCHS:
    EPOCHS[key] = sorted(EPOCHS[key])

try:
    fh = open('data3nf.csv', 'r') 
except FileNotFoundError:
    with open('data3nf.csv', "w") as csvfile:
        filewriter = csv.writer(csvfile, delimiter=',',quotechar='|', quoting=csv.QUOTE_MINIMAL)
        line1 = []
        for attribute in OUTER_ATTRIBUTES:
            line1.append(attribute)
        for attribute in ATTRIBUTES:
            line1.append(attribute)
        for flag in FLAGS:
            line1.append(flag)
        line1.append("label")
        filewriter.writerow(line1)
        FL += 1

def writer_good(node, label, filewriter):
    global FL
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
        row.append(label)
        filewriter.writerow(row)
        FL += 1

def writer_bad(node, filewriter, run_date, run_time, nodetype):
    global FL, LOGFILE
    idx = EPOCHS[run_date].index(run_time)
    startidx = 0
    if idx != 0:
        startidx = idx - 1
    else:
        startidx = idx
    starttime = EPOCHS[run_date][startidx]
    endtime = EPOCHS[run_date][idx]
    info = node['relays']
    for info_obj in info:
        row = []
        flag_list = info_obj['flags']
        fingerprint = info_obj['fingerprint']
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
        noerr = 0
        for line in LOGFILE:
            if run_date in line:
                elements = line.split(' ')
                error_msg = ""
                if starttime != endtime:
                    if starttime <= elements[1].split(',')[0] and elements[1].split(',')[0] <= endtime:
                        if 'ERROR' in elements:
                            if fingerprint in elements:
                                index = elements.index('ERROR')
                                error_msg = ' '.join(elements[index+1:])
                else:
                    if elements[1].split(',')[0] <= endtime:
                        if 'ERROR' in elements:
                            if fingerprint in elements:
                                index = elements.index('ERROR')
                                error_msg = ' '.join(elements[index+1:])
                if 'No such router' in error_msg:
                    error_msg = 'No such router\n'
                if 'No descriptor' in error_msg:
                    error_msg = 'No descriptor\n'
                if error_msg != "":
                    error_msg = nodetype + error_msg.strip('\n')
                    row.append(error_msg)
                    historic_bad.setdefault(fingerprint, []).append(error_msg)
                    # filewriter.writerow(row)
                    FL += 1
                else:
                    noerr = 1
        if len(row) and noerr == 0:
            print(fingerprint, row)

TOTAL = 0
with open('data3nf.csv', "a") as csvfile:
    filewriter = csv.writer(csvfile, delimiter=',',quotechar='|', quoting=csv.QUOTE_MINIMAL)
    for filename in glob.glob('./DC/MiddleRelayProfile*.json'):
        run_date = filename.split('MiddleRelayProfile')[1].split(' ')[0]
        run_time = filename.split('MiddleRelayProfile')[1].split(' ')[1].split('.')[0]
        print(filename)
        with open(filename) as rp:
            try:
                d = json.load(rp)
                middle_good = d['Middle']['Good']
                middle_bad = d['Middle']['Bad']
                print(filename, len(middle_bad), len(middle_good))
                TOTAL += len(middle_good) + len(middle_bad)
                for node in middle_good:
                    writer_good(node, 'middle_good', filewriter)
                for node in middle_bad:
                    writer_bad(node, filewriter, run_date, run_time, 'middle_bad: ')
                    writer_good(node, 'middle_bad', filewriter)
                    '''
                    try:
                        for n in node['relays']:
                            fp = str(n['fingerprint'])
                            historic_bad.setdefault(fp, 0)
                            historic_bad[fp] += 1
                    except Exception as e:
                        print(e)
                    '''
            except Exception as e:
                print("exception: ", e)
                exc_type, _, exc_tb = sys.exc_info()
                print(exc_type, exc_tb.tb_lineno, "\n\n")

print(TOTAL)
print(FL)


with open("bad_middle_freq.json", "w+") as f:
    json.dump(historic_bad, f)
