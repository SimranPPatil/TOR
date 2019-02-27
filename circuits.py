from stem import CircStatus
from stem.control import Controller
import stem.descriptor.remote
import random

hop1 = "C3777E3970FAC2C0CB2C4E166745A77650131304"
hop2 = "749EF4A434DFD00DAB31E93DE86233FB916D31E3"
exit = "8CF987FF43FB7F3D9AA4C4F3D96FFDF247A9A6C2"
relays = [hop1, hop2, exit]
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
'''

# port 9151 is the tor browser port
with Controller.from_port(port = 9151) as controller:
    controller.authenticate() 
    circuit_id = []
    for relay in random_middle:
        relays = [hop1, relay, exit]
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
