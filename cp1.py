'''
This script builds several two hop circuits and does failure measurements corresponding to each
'''

from stem import CircStatus, Flag
import stem.descriptor.remote
import random, time, StringIO, collections
import pycurl
import socks, socket,urllib
import stem.control
import stem.process
import logging
import matplotlib.pyplot as plt
import numpy as np

failures = []
# for logging the failures
logging.basicConfig(filename='failures.log',level=logging.DEBUG)

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

  output = StringIO.StringIO()

  query = pycurl.Curl()
  query.setopt(pycurl.URL, url)
  query.setopt(pycurl.PROXY, 'localhost')
  query.setopt(pycurl.PROXYPORT, SOCKS_PORT)
  query.setopt(pycurl.PROXYTYPE, pycurl.PROXYTYPE_SOCKS5_HOSTNAME)
  query.setopt(pycurl.CONNECTTIMEOUT, CONNECTION_TIMEOUT)
  query.setopt(pycurl.WRITEFUNCTION, output.write)

  try:
    query.perform()
    return output.getvalue()
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
    try:
        for desc in stem.descriptor.remote.get_consensus().run():
            if 'Running' in desc.flags:
                if 'Guard' in desc.flags:
                    guards.append(desc)
                if desc.exit_policy.is_exiting_allowed():
                    exits.setdefault(desc.bandwidth, []).append(desc)
    except Exception as exc:
        message = "Unable to retrieve the consensus: " + str(exc)
        logging.info(message)
    od = collections.OrderedDict(sorted(exits.items()))
    return od, guards

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


def build_circuits(PORT, exit_fixed_run, guard_fixed_run):
    exits, guards = get_relays()
    with stem.control.Controller.from_port(port = PORT) as controller:
        controller.authenticate()

        if exit_fixed_run:
            idx = 0
            for guard in guards:
                try:
                    if guard.fingerprint != fastexit:
                        idx += 1
                        try:
                            time_taken = scan(controller, [guard.fingerprint, fastexit])
                            print('| %s -- %s | => %0.2f seconds' % (guard.nickname,fe_nickname, time_taken))
                            message = guard.fingerprint + " => " + str(time_taken) + " seconds"
                            logging.info(message)
                        except Exception as exc:
                            message = guard.fingerprint + " => " + str(exc)
                            failures.append(str(exc))
                            logging.info(message)
                            print('%s => %s' % (guard.fingerprint, exc))
                except stem.InvalidRequest:
                    failures.append("No such router")
                    message = "No such router " + guard.fingerprint
                    logging.info(message)
            print_circuits(controller)
        else:
            for key in exits:
                for exit in exits[key]:
                    try:
                        if fastguard != exit.fingerprint:
                            try:
                                time_taken = scan(controller, [fastguard, exit.fingerprint])
                                print('| %s -- %s | => %0.2f seconds' % (fg_nickname, exit.nickname, time_taken))
                                message = exit.fingerprint + " => " + str(time_taken) + " seconds"
                                logging.info(message)
                            except Exception as exc:
                                message = exit.fingerprint + " => " + str(exc)
                                failures.append(str(exc))
                                logging.info(message)
                                print('%s => %s' % (exit.fingerprint, exc))
                    except stem.InvalidRequest:
                        failures.append("No such router")
                        message = "No such router " + str(exit.fingerprint)
                        logging.info(message)
            print_circuits(controller)

print("Run with exit fixed\n")
build_circuits(9051, True, False)

print(failures)
keys, counts = np.unique(failures, return_counts=True)

plt.bar(keys, counts)
plt.show()



print("Run with guard fixed\n")
#build_circuits(9051, False, True)
