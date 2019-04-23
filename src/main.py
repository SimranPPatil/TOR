'''
This script builds several two hop circuits and does failure measurements corresponding to each
'''

from stem import CircStatus, Flag
import stem
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
import hashlib

PAYLOAD_LINK = "https://n5.nz/100KiB"
PAYLOAD_HASH = "48936b426d70b36d633834782290a8d1af45a4d67c3c1d56704e50a0d045eed6"

# for info about the relays: https://onionoo.torproject.org/details?search=
# for logging the failures
FORMAT = '%(asctime)s %(levelname)-8s %(message)s'
# logging.Formatter(fmt='%(asctime)s %(levelname)-8s %(message)s',datefmt='%Y-%m-%d %H:%M:%S')
logging.basicConfig(filename='failures.log',
                    level=logging.DEBUG, format=FORMAT)
logging.info("\n")
logging.info(str(datetime.now()))

def hash_file(file_name):
    hasher = hashlib.sha256()
    with open(file_name,'rb') as afile:
        buf = afile.read()
        hasher.update(buf)
    return hasher.hexdigest()

def hash_bin(bins):
    hasher = hashlib.sha256()
    hasher.update(bins)
    return hasher.hexdigest()


def setup_custom_logging(name):
    formatter = logging.Formatter(fmt='%(asctime)s %(levelname)-8s %(message)s',
                                  datefmt='%Y-%m-%d %H:%M:%S')
    handler = logging.FileHandler('failures.log', mode="a+")
    handler.setFormatter(formatter)
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    return logger


# logger = setup_custom_logger('failures')
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
    start_build_timer = time.time()
    circuit_id = controller.new_circuit(path, await_build=True)
    ckt_build_time = time.time() - start_build_timer

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
            PAYLOAD_LINK, proxies=PROXIES)

        if hash_bin(check_page.content) != PAYLOAD_HASH:
            failures.append("WRONG DIGEST: Request didn't have the right content")
            raise ValueError("Request didn't have the right content")

        return time.time() - start_time, ckt_build_time
    finally:
        controller.remove_event_listener(attach_stream)
        controller.reset_conf('__LeaveStreamsUnattached')


# fetches the exit relays and other relays from the current consensus
# TODO: check for guard policy, if any
def get_relays():
    exits = {}
    guards = []
    AllExits = []
    try:
        for desc in stem.descriptor.remote.get_consensus().run():
            if 'Running' in desc.flags:
                if 'Guard' in desc.flags:
                    guards.append(desc)
                if desc.exit_policy.is_exiting_allowed():
                    AllExits.append(desc)
                    exits.setdefault(desc.bandwidth, []).append(desc)
    except Exception as exc:
        message = "Unable to retrieve the consensus: " + str(exc)
        logging.info(message)
    od = collections.OrderedDict(sorted(exits.items()))
    print("Guards fetched: ", len(guards))
    print("Exits fetched: ", len(AllExits))
    return od, guards, AllExits

def get_relays_middle():
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


def getFlags(Descflags, desc):
    flags = " ".join(desc.flags)
    message = desc.fingerprint + " => FLAGS: " + flags
    Descflags.setdefault(desc.fingerprint, []).append(desc.flags)


def getRelayInfo(desc):
    url = "https://onionoo.torproject.org/details?search=" + \
        str(desc.fingerprint)
    try:
        r = requests.get(url)
        return json.loads(r.text)
    except Exception as e:
        return {"exception": str(e)}


#
def test_circuit(guard, exit, controller, failure_log):
    try:
        time_taken, build_time = scan_requests(controller, [guard.fingerprint, exit.fingerprint], failure_log)
        print('| %s -- %s | => %0.2f seconds and %f' %
              (guard.nickname, exit.nickname, time_taken, build_time))
        message = guard.fingerprint + "--" + exit.fingerprint + " => " + str(time_taken) + " seconds " + str(build_time) + " seconds "
        logging.info(message)
        return 1
    except Exception as exc:
        # Custom Log
        if "invalid start byte" in str(exc):
            failure_log.append("invalid start byte")
        elif "invalid continuation byte" in str(exc):
            failure_log.append("invalid continuation byte")
        elif "No descriptor" in str(exc):
            failure_log.append("No descriptor")
        elif "No such router" in str(exc):
            failure_log.append("No such router")
        elif "Failed to establish a new connection" in str(exc):
            failure_log.append("Failed to establish a new connection")
        else:
            failure_log.append(str(exc))
        # Standard Log
        message = "%s => %s ERROR %s" % (
            guard.fingerprint, exit.fingerprint, str(exc))
        logging.info(message)
        return -1

def test_circuit_middle(guard, exit, middle, controller, failure_log):
    try:
        time_taken, build_time = scan_requests(controller, [guard.fingerprint, middle.fingerprint, exit.fingerprint], failure_log)
        print('| %s -- %s -- %s | => %0.2f seconds %f ' %
              (guard.nickname, middle.nickname, exit.nickname, time_taken, build_time))
        message = middle.fingerprint + " => " + str(time_taken) + " seconds " + str(build_time) + " seconds "
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
        elif "Failed to establish a new connection" in str(exc):
            failure_log.append("Failed to establish a new connection")
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
    relayProfile["Good"] = {}
    relayProfile["Bad"] = {}
    relayProfile["Bad"]["Guard"] = []
    relayProfile["Bad"]["Exit"] = []
    relayProfile["Good"]["Guard"] = []
    relayProfile["Good"]["Exit"] = []

    fixedGFailures = []
    fixedEFailures = []

    _, guards, AllExits = get_relays()
    with stem.control.Controller.from_port(port=PORT) as controller:
        controller.authenticate()
        # If fixedExit has been set
        if fixedExit != None:
            count = 0
            print("Run with exit fixed\n")
            for guard in guards:
                if limit != 0 and count > limit:
                    break
                count += 1
                rinfo = getRelayInfo(guard)
                try:
                    if FASTEXIT == guard.fingerprint:
                        continue
                    if test_circuit(guard, fixedExit, controller, fixedEFailures) > 0:
                        relayProfile["Good"]["Guard"].append(rinfo)
                    else:
                        relayProfile["Bad"]["Guard"].append(rinfo)
                except stem.InvalidRequest:
                    fixedEFailures.append("No such router")
                    message = "No such router " + guard.fingerprint
                    relayProfile["Bad"]["Guard"].append(rinfo)
                    logging.info(message)
            print_circuits(controller)
        # If fixedGuard has been set
        if fixedGuard != None:
            print("Run with guard fixed\n")
            # for key in exits:
            count = 0
            for exit in AllExits:
                if limit != 0 and count > limit:
                    break
                count += 1
                rinfo = getRelayInfo(exit)
                try:
                    if FASTGUARD == exit.fingerprint:
                        continue
                    if test_circuit(fixedGuard, exit, controller, fixedGFailures) > 0:
                        relayProfile["Good"]["Exit"].append(rinfo)
                    else:
                        relayProfile["Bad"]["Exit"].append(rinfo)
                except stem.InvalidRequest:
                    fixedGFailures.append("No such router")
                    message = "No such router " + str(exit.fingerprint)
                    relayProfile["Bad"]["Exit"].append(rinfo)
                    logging.info(message)
            print_circuits(controller)
    return relayProfile, fixedEFailures, fixedGFailures

def build_3hop_circuits(PORT, fixedExit, fixedGuard, limit=0):
    
    # Get JSON info about each relay node
    relayProfile = {}
    relayProfile["Middle"] = {}
    relayProfile["Middle"]["Good"] = []
    relayProfile["Middle"]["Bad"] = []

    MiddleFailures = []
    
    middle = get_relays_middle()
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
                    if test_circuit_middle(fixedGuard, fixedExit, relay, controller, MiddleFailures) > 0:
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

    relayProfile, fixedGFailures, fixedEFailures = build_circuits(9051, fixedExit, fixedGuard, limit=0)
    graphBuild(fixedGFailures, "DC/FixedGuard", 0)
    graphBuild(fixedEFailures, "DC/FixedExit", 1)
    print("FixedExit, bad guards: ", len(relayProfile["Bad"]["Guard"]))
    print("FixedGuard, bad exits: ", len(relayProfile["Bad"]["Exit"]))
    
    with open('DC/relayProfile' + str(datetime.now()) +'.json', 'w') as outfile:
        json.dump(relayProfile, outfile)

    relayProfile, MiddleFailures = build_3hop_circuits(9051, fixedExit, fixedGuard, limit=0)
    graphBuild(MiddleFailures, "DC/MiddleFailures", 0)
    print("bad middle relays: ", len(relayProfile["Middle"]["Bad"]))
    print("good middle relays: ", len(relayProfile["Middle"]["Good"]))
    with open('DC/MiddleRelayProfile' + str(datetime.now()) +'.json', 'w') as outfile:
        json.dump(relayProfile, outfile)
