from stem import CircStatus
from stem.control import Controller

hop1 = "C3777E3970FAC2C0CB2C4E166745A77650131304"
hop2 = "749EF4A434DFD00DAB31E93DE86233FB916D31E3"
exit = "8CF987FF43FB7F3D9AA4C4F3D96FFDF247A9A6C2"
relays = [hop1, hop2, exit]

# port 9151 is the tor browser port
with Controller.from_port(port = 9051) as controller:
    controller.authenticate() # we can look into authenticate if need be

    # should be able to build the circuits, TODO: streams if needed
    circuit_id = controller.new_circuit(relays, await_build = True)
    # builds the circuit we want with the set of relays specified and waits till the circuit is ready

    # look at destroy(circId)

    print(controller.get_circuit(circuit_id))
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
