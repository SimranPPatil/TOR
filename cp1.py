'''
This script builds several two hop circuits and does failure measurements corresponding to each
'''

from stem import CircStatus, Flag
import stem.descriptor.remote
import random
import time
import collections
# import pycurl
import io
import requests
# import socks
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
logging.basicConfig(filename='failures.log',
                    level=logging.DEBUG, format=FORMAT)
logging.info("\n")
logging.info(str(datetime.now()))


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

'''
def query(url, failures):
    """
    Uses pycurl to fetch a site using the proxy on the SOCKS_PORT.
    """

    #output = StringIO.StringIO()
    output = io.BytesIO()

    query = pycurl.Curl()
    query.setopt(pycurl.URL, url)
    query.setopt(pycurl.PROXY, 'localhost')
    query.setopt(pycurl.PROXYPORT, SOCKS_PORT)
    query.setopt(pycurl.PROXYTYPE, pycurl.PROXYTYPE_SOCKS5_HOSTNAME)
    query.setopt(pycurl.CONNECTTIMEOUT, CONNECTION_TIMEOUT)
    query.setopt(pycurl.WRITEFUNCTION, output.write)

    try:
        query.perform()
        return output.getvalue().decode('UTF-8')
    except pycurl.error as exc:
        message = "Unable to reach " + str(url) + " " + str(exc)
        failures.append(message)
        raise ValueError("Unable to reach %s (%s)" % (url, exc))


def scan(controller, path, failures):
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
        check_page = query('https://courses.engr.illinois.edu/ece428/sp2019/', failures)

        if 'Distributed Systems' not in check_page:
            failures.append("Request didn't have the right content")
            raise ValueError("Request didn't have the right content")

        return time.time() - start_time
    finally:
        controller.remove_event_listener(attach_stream)
        controller.reset_conf('__LeaveStreamsUnattached')
'''

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
            'https://courses.engr.illinois.edu/ece428/sp2019/')

        if 'Distributed Systems' not in check_page.text:
            failures.append("Request didn't have the right content")
            raise ValueError("Request didn't have the right content")

        return time.time() - start_time
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
    return od, guards, AllExits


def print_circuits(controller):
    for circ in sorted(controller.get_circuits()):
        if circ.status != CircStatus.BUILT:
            continue
        print("")
        print("Circuit %s (%s)" % (circ.id, circ.purpose))

        for i, entry in enumerate(circ.path):
            div = '+' if (i == len(circ.path) - 1) else '|'
            fingerprint, nickname = entry
            desc = controller.get_network_status(fingerprint, None)
            address = desc.address if desc else 'unknown'
            print(" %s- %s (%s, %s)" % (div, fingerprint, nickname, address))


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
        return {"exception": e}


#
def test_circuit(guard, exit, controller, failure_log):
    try:
        time_taken = scan_requests(controller, [guard.fingerprint, exit.fingerprint], failure_log)
        print('| %s -- %s | => %0.2f seconds' %
              (guard.nickname, exit.nickname, time_taken))
        message = exit.fingerprint + " => " + str(time_taken) + " seconds"
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
        else:
            failure_log.append(str(exc))
        # Standard Log
        message = "%s => %s ERROR %s" % (
            guard.fingerprint, exit.fingerprint, str(exc))
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

    exits, guards, AllExits = get_relays()
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
        print("COULD NOT FIND FIXEDEXIT OR FIXEDRELAY")
        exit()

    relayProfile, fixedGFailures, fixedEFailures = build_circuits(9051, fixedExit, fixedGuard, 30)
    graphBuild(fixedGFailures, "FixedGuard", 0)
    graphBuild(fixedEFailures, "FixedExit", 1)
    print("FixedExit, bad guards: ", len(relayProfile["Bad"]["Guard"]))
    print("FixedGuard, bad exits: ", len(relayProfile["Bad"]["Exit"]))
    
    with open('relayProfile' + str(datetime.now()) +'.json', 'w') as outfile:
        json.dump(relayProfile, outfile)
