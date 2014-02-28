"""
ape example: ping servers

simple example to create and send request to agents.
a reply is sent but this example doesn't listen for it.
to see anything happening, make sure the container is using DEBUG logging for ape messages,
and watch the container logs.

"""

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
    m = SimpleManager(broker_hostname='localhost', broker_username='guest', broker_password='guest')

    print 'sending 100 ping requests to all components on all agents, one every 5 seconds'
    for n in xrange(100):
        m.send_request(p)
        print 'sent a ping'
        sleep(5)
    print 'sending complete'
    wait(2)

if __name__ == "__main__":
    main()