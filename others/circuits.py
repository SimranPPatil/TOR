from stem import CircStatus
from stem.control import Controller
import stem.descriptor.remote
import random
import time, io
import socks  # SocksiPy module
import socket
import urllib
import stem.control
import stem.process

hop1 = "C3777E3970FAC2C0CB2C4E166745A77650131304"
exit = "749EF4A434DFD00DAB31E93DE86233FB916D31E3"
num_circuits = 10

fingerprints = []
try:
  for desc in stem.descriptor.remote.get_consensus():
    fingerprints.append(desc.fingerprint)
except Exception as exc:
  print("Unable to retrieve the consensus: %s" % exc)

random_middle = random.sample(fingerprints, num_circuits)
print(random_middle)

'''
with Controller.from_port(port = 9151) as controller:
  controller.authenticate()

  for desc in controller.get_network_statuses():
    print("found relay %s (%s)" % (desc.nickname, desc.fingerprint))

# provides a mapping of observed bandwidth to the relay nicknames
def get_bw_to_relay():
  bw_to_relay = {}

  try:
    for desc in stem.descriptor.remote.get_server_descriptors().run():
      if desc.exit_policy.is_exiting_allowed():
        bw_to_relay.setdefault(desc.observed_bandwidth, []).append(desc.nickname)
  except Exception as exc:
    print("Unable to retrieve the server descriptors: %s" % exc)

  return bw_to_relay
'''


'''
# Perform DNS resolution through the socket <-- Does it go through tor? else location can be known
def getaddrinfo(*args):
  return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (args[0], args[1]))]
socket.getaddrinfo = getaddrinfo
'''

SOCKS_PORT = 9151
CONNECTION_TIMEOUT = 30  # timeout before we give up on a circuit

def query(url):
  """
  Uses pycurl to fetch a site using the proxy on the SOCKS_PORT.
  """

  output = io.StringIO()

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
    check_page = query('https://check.torproject.org/')

    if 'Congratulations. This browser is configured to use Tor.' not in check_page:
      raise ValueError("Request didn't have the right content")

    return time.time() - start_time
  finally:
    controller.remove_event_listener(attach_stream)
    controller.reset_conf('__LeaveStreamsUnattached')

'''
# port 9151 is the tor browser port
with Controller.from_port(port = 9151) as controller:
    controller.authenticate()
    circuit_id = []
    for relay in random_middle:
        relays = [hop1, relay, exit]
        # It does not check if the relays are from the same family
        # this is vanilla circuit creation
        circuit_id.append(controller.new_circuit(relays, await_build = True))

    for circ in sorted(controller.get_circuits()):
        if circ.status != CircStatus.BUILT:
          continue

        print("")
        print("Circuit %s (%s)" % (circ.id, circ.purpose))
        # controller.close_circuit(circ.id)
        for i, entry in enumerate(circ.path):
          div = '+' if (i == len(circ.path) - 1) else '|'
          fingerprint, nickname = entry

          desc = controller.get_network_status(fingerprint, None)
          address = desc.address if desc else 'unknown'

          print(" %s- %s (%s, %s)" % (div, fingerprint, nickname, address))

'''

with stem.control.Controller.from_port(port = 9151) as controller:
    controller.authenticate()
    for relay in random_middle:
        relays = [hop1, relay, exit]
        # It does not check if the relays are from the same family
        # this is vanilla circuit creation
        try:
          time_taken = scan(controller, relays)
          print('%s => %0.2f seconds' % (relay, time_taken))
        except Exception as exc:
          print('%s => %s' % (relay, exc))

    for circ in sorted(controller.get_circuits()):
        if circ.status != CircStatus.BUILT:
          continue
        print("")
        print("Circuit %s (%s)" % (circ.id, circ.purpose))
        # controller.close_circuit(circ.id)
        for i, entry in enumerate(circ.path):
          div = '+' if (i == len(circ.path) - 1) else '|'
          fingerprint, nickname = entry

          desc = controller.get_network_status(fingerprint, None)
          address = desc.address if desc else 'unknown'

          print(" %s- %s (%s, %s)" % (div, fingerprint, nickname, address))
tor_process.kill()  # stops tor
