import gevent.monkey
from ape.component.transform import TransformComponent
from ape.component.transform import Configuration as TransformConfiguration
from ape.manager.troop import Troop

gevent.monkey.patch_all(aggressive=False)

from ape.manager.simple_manager import SimpleManager, InventoryListener, Listener
from ape.common.requests import PingRequest, AddComponent, StartRequest, InventoryRequest, StopRequest, PerformanceResult
from ape.component.instrument_simulator import InstrumentSimulator
from ape.component.instrument_simulator import Configuration as InstrumentConfiguration
from ape.component.consumer import DataProductConsumer
from ape.component.consumer import Configuration as ConsumerConfiguration
from ape.common.messages import  component_id, agent_id, component_type
from time import sleep
import math
from numpy import array, zeros

def wait(a):
    raw_input('--- press enter to continue ---')

def main():
    print 'defining a launch plan'
    t = Troop(clobber=True)
    t.configure('resources/three-containers.trp')
    t.create_launch_plan()
    print 'created a launch plan with %d containers' % t.get_container_count()

    l = InventoryListener()
    m = SimpleManager()
    m.add_listener(l)

    m.send_request(InventoryRequest())
    print 'requested inventory -- waiting for reply messages'
    sleep(5)

    print 'inventory before nodes are started: '
    show_inventory(l.inventory)

    print 'now starting nodes'
    t.start_nodes()

    # get inventory -- see what agents we have running
    m.send_request(InventoryRequest())
    print 'requested inventory again -- waiting for reply messages'
    sleep(5)

    print 'inventory after nodes have started: '
    show_inventory(l.inventory)

    print 'now stopping nodes'
    t.stop_nodes()


def show_inventory(i):
    if not i:
        print 'None'
    for key in i.keys():
        print 'agent ' + key + ':'
        print i[key]

if __name__ == "__main__":
    main()
