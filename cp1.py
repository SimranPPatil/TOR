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

failedExits = {}
failedGuards = {}
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
fastguard = "5CECC5C30ACC4B3DE462792323967087CC53D947"
fg_nickname = "PrivacyRepublic0001"

# https://metrics.torproject.org/rs.html#details/BC630CBBB518BE7E9F4E09712AB0269E9DC7D626
fastexit = "BC630CBBB518BE7E9F4E09712AB0269E9DC7D626"
fe_nickname = "IPredator"

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

    check_page = query('https://www.google.com/')

    if 'google' not in check_page:
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


def build_circuits(PORT, exit_fixed_run, guard_fixed_run):
    exits, guards, AllExits = get_relays()
    with stem.control.Controller.from_port(port = PORT) as controller:
        controller.authenticate()

        if exit_fixed_run:
            for guard in guards:
                try:
                    if guard.fingerprint != fastexit:
                        try:
                            time_taken = scan(controller, [guard.fingerprint, fastexit])
                            print('| %s -- %s | => %0.2f seconds' % (guard.nickname,fe_nickname, time_taken))
                            message = guard.fingerprint + " => " + str(time_taken) + " seconds"
                            logging.info(message)
                        except Exception as exc:
                            failures.append(str(exc))
                            message = guard.fingerprint + " => " + str(exc)
                            logging.info(message)
                            failedGuards[guard.fingerprint] = getRelayInfo(guard)
                            print('%s => %s ' % (guard.fingerprint, exc))
                except stem.InvalidRequest:
                    failures.append("No such router")
                    message = "No such router " + guard.fingerprint
                    failedGuards[guard.fingerprint] = getRelayInfo(guard)
                    logging.info(message)
            print_circuits(controller)
        else:
            #for key in exits:
            for exit in AllExits:
                try:
                    if fastguard != exit.fingerprint:
                        try:
                            time_taken = scan(controller, [fastguard, exit.fingerprint])
                            print('| %s -- %s | => %0.2f seconds' % (fg_nickname, exit.nickname, time_taken))
                            message = exit.fingerprint + " => " + str(time_taken) + " seconds"
                            logging.info(message)
                        except Exception as exc:
                            if "invalid start byte" in str(exc):
                                failures.append("invalid start byte")
                            elif "invalid continuation byte" in str(exc):
                                failures.append("invalid continuation byte")
                            else:
                                failures.append(str(exc))
                            message = exit.fingerprint + " => " + str(exc)
                            logging.info(message)
                            failedExits[exit.fingerprint] = getRelayInfo(exit)
                            print('%s => %s' % (exit.fingerprint, exc))
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

#failures = ['Circuit failed to be created: TIMEOUT', 'Circuit failed to be created: DESTROYED', 'Circuit failed to be created: DESTROYED', 'Circuit failed to be created: TIMEOUT', 'Circuit failed to be created: DESTROYED', 'Circuit failed to be created: TIMEOUT', 'Circuit failed to be created: DESTROYED', 'Circuit failed to be created: TIMEOUT', 'Circuit failed to be created: DESTROYED', 'Circuit failed to be created: DESTROYED', 'Circuit failed to be created: CHANNEL_CLOSED', 'Circuit failed to be created: TIMEOUT', 'Circuit failed to be created: TIMEOUT', 'Circuit failed to be created: TIMEOUT', 'Circuit failed to be created: DESTROYED', 'Circuit failed to be created: DESTROYED', 'Circuit failed to be created: TIMEOUT', "Unable to reach https://www.google.com/ (35, 'LibreSSL SSL_connect: SSL_ERROR_SYSCALL in connection to www.google.com:443 ')", "Unable to reach https://www.google.com/ ((35, 'LibreSSL SSL_connect: SSL_ERROR_SYSCALL in connection to www.google.com:443 '))", 'Circuit failed to be created: TIMEOUT', 'Circuit failed to be created: TIMEOUT', 'Circuit failed to be created: TIMEOUT', 'Circuit failed to be created: CHANNEL_CLOSED', 'Circuit failed to be created: TIMEOUT', 'Circuit failed to be created: TIMEOUT', 'Circuit failed to be created: TIMEOUT', 'Circuit failed to be created: DESTROYED', 'Circuit failed to be created: DESTROYED', 'Circuit failed to be created: DESTROYED', 'Circuit failed to be created: DESTROYED', 'Circuit failed to be created: DESTROYED', 'Circuit failed to be created: DESTROYED', 'Circuit failed to be created: TIMEOUT', 'Circuit failed to be created: TIMEOUT', 'Circuit failed to be created: DESTROYED', 'Circuit failed to be created: TIMEOUT', 'Circuit failed to be created: TIMEOUT', 'Circuit failed to be created: TIMEOUT', 'Circuit failed to be created: TIMEOUT', 'Circuit failed to be created: TIMEOUT', 'Circuit failed to be created: DESTROYED', 'Circuit failed to be created: TIMEOUT', 'Circuit failed to be created: DESTROYED', 'Circuit failed to be created: TIMEOUT', 'Circuit failed to be created: TIMEOUT', 'Circuit failed to be created: TIMEOUT', 'Circuit failed to be created: TIMEOUT', 'Circuit failed to be created: DESTROYED', 'Circuit failed to be created: TIMEOUT', 'Circuit failed to be created: DESTROYED', 'Circuit failed to be created: TIMEOUT', 'Circuit failed to be created: TIMEOUT', 'Circuit failed to be created: DESTROYED', 'Circuit failed to be created: TIMEOUT', 'Circuit failed to be created: DESTROYED', 'Circuit failed to be created: TIMEOUT', 'Circuit failed to be created: TIMEOUT', 'Circuit failed to be created: TIMEOUT', 'Circuit failed to be created: TIMEOUT', 'Circuit failed to be created: TIMEOUT', 'Circuit failed to be created: TIMEOUT', 'Circuit failed to be created: DESTROYED', 'Circuit failed to be created: TIMEOUT', 'Circuit failed to be created: TIMEOUT', 'Circuit failed to be created: DESTROYED', 'Circuit failed to be created: TIMEOUT', 'Circuit failed to be created: DESTROYED', 'Circuit failed to be created: TIMEOUT', 'Circuit failed to be created: DESTROYED', 'Circuit failed to be created: TIMEOUT', 'Circuit failed to be created: DESTROYED', 'Circuit failed to be created: TIMEOUT', 'Circuit failed to be created: DESTROYED', 'Circuit failed to be created: TIMEOUT', 'Circuit failed to be created: TIMEOUT', 'Circuit failed to be created: TIMEOUT', 'No such router "D5B8C38539C509380767D4DE20DE84CF84EE8299"', 'Circuit failed to be created: DESTROYED', 'Circuit failed to be created: TIMEOUT', 'Circuit failed to be created: TIMEOUT', 'Circuit failed to be created: DESTROYED', 'Circuit failed to be created: TIMEOUT', 'Circuit failed to be created: TIMEOUT', 'Circuit failed to be created: TIMEOUT', 'Circuit failed to be created: TIMEOUT', 'Circuit failed to be created: TIMEOUT', "Unable to reach https://www.google.com/ (7, 'Failed to receive SOCKS5 connect request ack.')", "Unable to reach https://www.google.com/ ((7, 'Failed to receive SOCKS5 connect request ack.'))", 'Circuit failed to be created: TIMEOUT', 'Circuit failed to be created: TIMEOUT', 'Circuit failed to be created: TIMEOUT', 'Circuit failed to be created: TIMEOUT', 'Circuit failed to be created: TIMEOUT', 'Circuit failed to be created: TIMEOUT', 'Circuit failed to be created: TIMEOUT', 'Circuit failed to be created: TIMEOUT', 'Circuit failed to be created: DESTROYED']
failures = []
print("Run with exit fixed\n")
build_circuits(9051, True, False)
graphBuild(failures, "FF_exit_")
print(failedGuards)

failures = []
print("Run with guard fixed\n")
build_circuits(9051, False, True)
graphBuild(failures, "FF_guard_")
print(failedExits)
