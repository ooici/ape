import gevent.monkey

gevent.monkey.patch_all(aggressive=False)

from ape.manager.simple_manager import SimpleManager
from ape.common.requests import PingRequest, AddComponent, InventoryRequest
from ape.component.instrument_simulator import InstrumentSimulator
from ape.component.instrument_simulator import Configuration as InstrumentConfiguration
from ape.common.messages import  component_id
from time import sleep

def wait(a):
    raw_input('--- press enter to continue ---')
#    sleep(a)

def main():
    m = SimpleManager()

    m.send_request(InventoryRequest(), component_filter=component_id('AGENT'))
    print '---> sent inventory request'
    sleep(2)

    print '---> inventory now:\n'
    show_inventory(m.inventory)
    wait(10)

    sim1 = InstrumentSimulator('ins1', None, InstrumentConfiguration('str1', 0.05))
    r1 = AddComponent(sim1)
    m.send_request(r1)
    print 'creating sim1'
#    sleep(5)

    sim2 = InstrumentSimulator('ins2', None, InstrumentConfiguration('str2', 0))
    r2 = AddComponent(sim2)
    m.send_request(r2, component_filter=component_id('AGENT'))
    print 'creating sim2'
    print '---> created 2 instruments'
    sleep(5)

    m.send_request(InventoryRequest(), component_filter=component_id('AGENT'))
    print '---> sent inventory request'
    sleep(2)

    print '---> inventory now:\n'
    show_inventory(m.inventory)
    wait(10)
    show_inventory(m.inventory)
    wait(10)

def show_inventory(i):
    for key in i.keys():
        print 'agent ' + key + ':'
        print i[key]

if __name__ == "__main__":
    main()