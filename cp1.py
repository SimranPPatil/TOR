'''
This script builds several two hop circuits and does failure measurements corresponding to each
'''

from stem import CircStatus, Flag
import stem.descriptor.remote
import random, time, io, collections
import socks, socket,urllib
import stem.control
import stem.process

# https://metrics.torproject.org/rs.html#details/5CECC5C30ACC4B3DE462792323967087CC53D947
fastguard = "5CECC5C30ACC4B3DE462792323967087CC53D947"

# https://metrics.torproject.org/rs.html#details/BC630CBBB518BE7E9F4E09712AB0269E9DC7D626
fastexit = "BC630CBBB518BE7E9F4E09712AB0269E9DC7D626"

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
        print("Unable to retrieve the consensus: %s" % exc)
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
            for guard in guards:
                try:
                    circuit_id = controller.new_circuit([guard.fingerprint, fastexit])
                except stem.InvalidRequest:
                    print("No such router ", guard.fingerprint)
            print_circuits(controller)
        else:
            for key in exits:
                for exit in exits[key]:
                    try:
                        circuit_id = controller.new_circuit([fastguard, exit.fingerprint])
                    except stem.InvalidRequest:
                        print("No such router ", exit.fingerprint)
            print_circuits(controller)

build_circuits(9051, False, True)
