'''
This script builds several two hop circuits and does failure measurements corresponding to each

Task: Checking middle relay reliability, building three hop circuits
'''

from stem import CircStatus, Flag
import stem.descriptor.remote
import random
import time
import collections
import io
import requests
import socket
import urllib
import stem.control
import stem.process
import logging
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime


# for info about the relays: https://onionoo.torproject.org/details?search=
# for logging the failures
FORMAT = '%(asctime)s %(levelname)-8s %(message)s'
# logging.Formatter(fmt='%(asctime)s %(levelname)-8s %(message)s',datefmt='%Y-%m-%d %H:%M:%S')
logging.basicConfig(filename='failures3.log',
                    level=logging.DEBUG, format=FORMAT)
logging.info("\n")
logging.info(str(datetime.now()))

# https://metrics.torproject.org/rs.html#details/5CECC5C30ACC4B3DE462792323967087CC53D947
FASTGUARD = "5CECC5C30ACC4B3DE462792323967087CC53D947"
FG_NICKNAME = "PrivacyRepublic0001"

# https://metrics.torproject.org/rs.html#details/BC630CBBB518BE7E9F4E09712AB0269E9DC7D626
FASTEXIT = "BC630CBBB518BE7E9F4E09712AB0269E9DC7D626"
FE_NICKNAME = "IPredator"

SOCKS_PORT = 9050
CONNECTION_TIMEOUT = 30  # timeout before we give up on a circuit
PROXIES = {
    'http':'socks5h://127.0.0.1:'+str(SOCKS_PORT),
    'https':'socks5h://127.0.0.1:'+str(SOCKS_PORT)
}

def scan_requests(controller, path, failures):
    """
    Fetch check.torproject.org through the given path of relays, providing back
    the time it took.
    """

    circuit_id = controller.new_circuit(path, await_build=True)

    def attach_stream(stream):
        if stream.status == 'NEW':
            controller.attach_stream(stream.id, circuit_id)

    controller.add_event_listener(attach_stream, stem.control.EventType.STREAM)

    try:
        # leave stream management to us
        controller.set_conf('__LeaveStreamsUnattached', '1')
        start_time = time.time()

        # check_page = query('https://www.google.com/')
        check_page = requests.get(
            'https://courses.engr.illinois.edu/ece428/sp2019/', proxies=PROXIES)

        if 'Distributed Systems' not in check_page.text:
            failures.append("Request didn't have the right content")
            raise ValueError("Request didn't have the right content")

        return time.time() - start_time
    finally:
        controller.remove_event_listener(attach_stream)
        controller.reset_conf('__LeaveStreamsUnattached')


# fetches the middle relays from the current consensus
def get_relays():
    middle = []
    try:
        for desc in stem.descriptor.remote.get_consensus().run():
            if 'Running' in desc.flags:
                middle.append(desc)
    except Exception as exc:
        message = "Unable to retrieve the consensus: " + str(exc)
        logging.info(message)
    print("Relays fetched: ", len(middle))
    return middle


def print_circuits(controller):
    count = 0
    print("Circuits: ", len(controller.get_circuits()))
    for circ in sorted(controller.get_circuits()):
        if circ.status != CircStatus.BUILT:
            continue
        print("")
        print("Circuit %s (%s)" % (circ.id, circ.purpose))

        for i, entry in enumerate(circ.path):
            count += 1
            div = '+' if (i == len(circ.path) - 1) else '|'
            fingerprint, nickname = entry
            desc = controller.get_network_status(fingerprint, None)
            address = desc.address if desc else 'unknown'
            print(" %s- %s (%s, %s)" % (div, fingerprint, nickname, address))
    print("circuits built: ", count)


def getRelayInfo(desc):
    url = "https://onionoo.torproject.org/details?search=" + \
        str(desc.fingerprint)
    try:
        r = requests.get(url)
        return json.loads(r.text)
    except Exception as e:
        return {"exception": str(e)}


def test_circuit(guard, exit, middle, controller, failure_log):
    try:
        time_taken = scan_requests(controller, [guard.fingerprint, middle.fingerprint, exit.fingerprint], failure_log)
        print('| %s -- %s -- %s | => %0.2f seconds' %
              (guard.nickname, middle.nickname, exit.nickname, time_taken))
        message = middle.fingerprint + " => " + str(time_taken) + " seconds"
        logging.info(message)
        return 1
    except Exception as exc:
        # Custom Log for graph
        if "invalid start byte" in str(exc):
            failure_log.append("invalid start byte")
        elif "invalid continuation byte" in str(exc):
            failure_log.append("invalid continuation byte")
        elif "No descriptor" in str(exc):
            failure_log.append("No descriptor")
        elif "No such router" in str(exc):
            failure_log.append("No such router")
        else:
            failure_log.append(str(exc))
        # Standard Log
        message = "%s => ERROR %s" % (
            middle.fingerprint, str(exc))
        logging.info(message)
        return -1


def build_circuits(PORT, fixedExit, fixedGuard, limit=0):
    
    # Get JSON info about each relay node
    relayProfile = {}
    relayProfile["Middle"] = {}
    relayProfile["Middle"]["Good"] = []
    relayProfile["Middle"]["Bad"] = []

    MiddleFailures = []
    
    middle = get_relays()
    with stem.control.Controller.from_port(port=PORT) as controller:
        controller.authenticate()
        if fixedExit != None and fixedGuard != None:
            count = 0
            print("3 Hop: Run with guard and exit fixed\n")
            for relay in middle:
                if limit != 0 and count > limit:
                    break
                count += 1
                rinfo = getRelayInfo(relay)
                try:
                    if FASTEXIT == relay.fingerprint or FASTGUARD == relay.fingerprint or FASTEXIT == FASTGUARD:
                        continue
                    if test_circuit(fixedGuard, fixedExit, relay, controller, MiddleFailures) > 0:
                        relayProfile["Middle"]["Good"].append(rinfo)
                    else:
                        relayProfile["Middle"]["Bad"].append(rinfo)
                except stem.InvalidRequest:
                    MiddleFailures.append("No such router")
                    message = "No such router " + relay.fingerprint
                    relayProfile["Middle"]["Bad"].append(rinfo)
                    logging.info(message)
            print_circuits(controller)
        
    return relayProfile, MiddleFailures


def graphBuild(failures, name, fig_number):
    '''
    plt.ylim(top=np.amax(counts))
    for i in range(len(labels)):
        txt = str(labels[i]) + ": " + keys[i]
        plt.text(0, np.amax(counts) - 2 - i * 5, txt, fontsize=6, wrap=True)
    '''
    keys, counts = np.unique(failures, return_counts=True)
    labels = np.arange(len(keys))

    index_to_key = {}
    for i in range(len(keys)):
        index_to_key[i] = {}
        index_to_key[i]["key"] = keys[i]
        index_to_key[i]["frequency"] = str(counts[i])
    print(index_to_key)

    plt.figure(fig_number)
    l = []
    for label in labels:
      l.append(str(label))
    plt.bar(l, counts)
    plt.xlabel('Types of Failures')
    plt.ylabel('Frequency')
    figname = name + str(datetime.now())
    plt.savefig(figname + ".png")
    with open(figname + ".txt", 'w') as outfile:
        json.dump(index_to_key, outfile)

if __name__ == "__main__":

    # get descriptor for the fixed relay
    fixedExit = None
    fixedGuard = None

    for desc in stem.descriptor.remote.get_server_descriptors():
        if desc.nickname == FE_NICKNAME and desc.fingerprint == FASTEXIT:
            fixedExit = desc
        elif desc.nickname == FG_NICKNAME and desc.fingerprint == FASTGUARD:
            fixedGuard = desc

    # check if fixed exit and fixed guard exists
    if fixedExit == None or fixedGuard == None:
        print("COULD NOT FIND FIXEDEXIT OR FIXEDGUARD")
        exit()

    relayProfile, MiddleFailures = build_circuits(9051, fixedExit, fixedGuard)
    graphBuild(MiddleFailures, "DC/MiddleFailures", 0)
    print("bad middle relays: ", len(relayProfile["Middle"]["Bad"]))
    print("good middle relays: ", len(relayProfile["Middle"]["Good"]))
    
    with open('DC/MiddleRelayProfile' + str(datetime.now()) +'.json', 'w') as outfile:
        json.dump(relayProfile, outfile)
