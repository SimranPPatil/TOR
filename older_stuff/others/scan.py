import io
import time
import stem.control

# Static exit for us to make 2-hop circuits through. Picking aurora, a
# particularly beefy one...
#
#   https://metrics.torproject.org/rs.html#details/379FB450010D17078B3766C2273303C358C3A442

EXIT_FINGERPRINT = "749EF4A434DFD00DAB31E93DE86233FB916D31E3"

import socks  # SocksiPy module
import socket
import urllib

SOCKS_PORT = 9151

# Set socks proxy and wrap the urllib module

socks.setdefaultproxy(socks.PROXY_TYPE_SOCKS5, 'localhost', SOCKS_PORT)
socket.socket = socks.socksocket

# Perform DNS resolution through the socket

def getaddrinfo(*args):
  return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (args[0], args[1]))]

socket.getaddrinfo = getaddrinfo

def query(url):
  """
  Uses urllib to fetch a site using SocksiPy for Tor over the SOCKS_PORT.
  """

  try:
    return urllib.urlopen(url).read()
  except:
    return "Unable to reach %s" % url

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


with stem.control.Controller.from_port(port = 9151) as controller:
  controller.authenticate()

  relay_fingerprints = [desc.fingerprint for desc in controller.get_network_statuses()]

  for fingerprint in relay_fingerprints:
    try:
      time_taken = scan(controller, [fingerprint, EXIT_FINGERPRINT])
      print('%s => %0.2f seconds' % (fingerprint, time_taken))
    except Exception as exc:
      print('%s => %s' % (fingerprint, exc))
