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
    pass

def main():
    p = PingRequest()
    m = SimpleManager()

    print 'sending 100 ping requests to all components on all agents'
    for n in xrange(100):
        m.send_request(p)
        sleep(5)
    print '--- sent pings ----'
    wait(2)

if __name__ == "__main__":
    main()