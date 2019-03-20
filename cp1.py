'''
This script builds several two hop circuits and does failure measurements corresponding to each
'''

from stem import CircStatus, Flag
import stem.descriptor.remote
import random, time, collections
import pycurl, io, requests
import socks, socket,urllib
import stem.control
import stem.process
import logging, json
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime


# for info about the relays: https://onionoo.torproject.org/details?search=
# for logging the failures
FORMAT = '%(asctime)s %(levelname)-8s %(message)s'
# logging.Formatter(fmt='%(asctime)s %(levelname)-8s %(message)s',datefmt='%Y-%m-%d %H:%M:%S')
logging.basicConfig(filename='failures.log',level=logging.DEBUG, format=FORMAT)
logging.info("\n")
logging.info(str(datetime.now()))

def setup_custom_logging(name):
    formatter = logging.Formatter(fmt='%(asctime)s %(levelname)-8s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S')
    handler = logging.FileHandler('failures.log', mode = "a+")
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
FE_NICKNAME= "IPredator"

SOCKS_PORT = 9050
CONNECTION_TIMEOUT = 30  # timeout before we give up on a circuit

def query(url):
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


def scan(controller, path):
    """
    Fetch check.torproject.org through the given path of relays, providing back
    the time it took.
    """

    circuit_id = controller.new_circuit(path, await_build = True)

    def attach_stream(stream):
        if stream.status == 'NEW':
            controller.attach_stream(stream.id, circuit_id)

    controller.add_event_listener(attach_stream, stem.control.EventType.STREAM)

    try:
        controller.set_conf('__LeaveStreamsUnattached', '1')  # leave stream management to us
        start_time = time.time()

        # check_page = query('https://www.google.com/')
        check_page = query('https://courses.engr.illinois.edu/ece428/sp2019/')

        if 'Distributed Systems' not in check_page:
            failures.append("Request didn't have the right content")
            raise ValueError("Request didn't have the right content")

        return time.time() - start_time
    finally:
        controller.remove_event_listener(attach_stream)
        controller.reset_conf('__LeaveStreamsUnattached')


def scan_requests(controller, path):
  """
  Fetch check.torproject.org through the given path of relays, providing back
  the time it took.
  """

  circuit_id = controller.new_circuit(path, await_build = True)

  def attach_stream(stream):
    if stream.status == 'NEW':
      controller.attach_stream(stream.id, circuit_id)

  controller.add_event_listener(attach_stream, stem.control.EventType.STREAM)

  try:
    controller.set_conf('__LeaveStreamsUnattached', '1')  # leave stream management to us
    start_time = time.time()

    # check_page = query('https://www.google.com/')
    check_page = requests.get('https://courses.engr.illinois.edu/ece428/sp2019/')

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
    message = desc.fingerprint + " => FLAGS: "+ flags
    Descflags.setdefault(desc.fingerprint, []).append(desc.flags)

def getRelayInfo(desc):
    url = "https://onionoo.torproject.org/details?search=" + str(desc.fingerprint)
    try:
        r = requests.get(url)
        return json.loads(r.text)
    except Exception as e:
        return {"exception" : e}


#
def test_circuit(guard, exit, controller, failure_log, relay_log):
    try:
    	time_taken = scan_requests(controller, [guard, exit.fingerprint])
    	print('| %s -- %s | => %0.2f seconds' % (fg_nickname, exit.nickname, time_taken))
    	message = exit.fingerprint + " => " + str(time_taken) + " seconds"
    	logging.info(message)
    except Exception as exc:
        # Custom Log
    	if "invalid start byte" in str(exc):
    	    failure_log.append("invalid start byte")
    	elif "invalid continuation byte" in str(exc):
    	    failure_log.append("invalid continuation byte")
    	else:
    	    failure_log.append(str(exc))
        # Standard Log
        message="%s => %s ERROR %s"%(guard.fingerprint, exit.fingerprint, str(exc))
        logging.info(message)

        relay_log[exit.fingerprint] = getRelayInfo(exit)
        print(message)
    	#print('%s => %s' % (exit.fingerprint, exc))


def build_circuits(PORT, fixedExit, fixedGuard, failedGuards, failedExits):
    exits, guards, AllExits = get_relays()
    with stem.control.Controller.from_port(port = PORT) as controller:
        controller.authenticate()
        # If fixedExit has been set
        if fixedExit != None:
            for guard in guards:
                try:
                    test_circuit(guard, fixedExit, controller, failures, failedGuards)
                except stem.InvalidRequest:
                    failures.append("No such router")
                    message = "No such router " + guard.fingerprint
                    failedGuards[guard.fingerprint] = getRelayInfo(guard)
                    logging.info(message)
            print_circuits(controller)
        # If fixedGuard has been set
        elif fixedGuard != None:
            #for key in exits:
            for exit in AllExits:
                try:
                    if FASTGUARD != exit.fingerprint:
                        test_circuit(FASTGUARD, exit, controller, failures, failedExits)
                except stem.InvalidRequest:
                    failures.append("No such router")
                    message = "No such router " + str(exit.fingerprint)
                    failedExits[exit.fingerprint] = getRelayInfo(exit)
                    logging.info(message)
            print_circuits(controller)


def graphBuild(failures, name):
    keys, counts = np.unique(failures, return_counts=True)
    labels = np.arange(len(keys))
    plt.ylim(top=np.amax(counts))
    plt.bar(labels, counts, width=0.4)
    plt.xlabel('Types of Failures')
    plt.ylabel('Frequency')
    for i in range(len(labels)):
        txt = str(labels[i]) + ": " + keys[i]
        plt.text(0, np.amax(counts)-2-i*5, txt, fontsize=6, wrap=True)
    figname = name+str(datetime.now()) + ".png"
    plt.savefig(figname)




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
 
    failedExits = {}
    failedGuards = {}

    failures = []
    print("Run with exit fixed\n")
    build_circuits(9051, fixedExit, None, failedGuards, failedExits)
    graphBuild(failures, "FF_exit_")
    print(failedGuards)


    exit()

    failures = []
    print("Run with guard fixed\n")
    build_circuits(9051, False, True)
    graphBuild(failures, "FF_guard_")
    print(failedExits)
