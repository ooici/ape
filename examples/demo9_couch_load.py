"""
ape sample: publish/subscribe

create an InstrumentSimulator component which registers a new data product and creates messages at a specified rate,
and a DataProductConsumer component that receives these messages and discards (optionally prints) them.
although the pair of ape components are created on each agent found,
the actual processes are requested from the system and could be launched in a different container entirely.
"""
from threading import Lock

import gevent.monkey

gevent.monkey.patch_all(aggressive=False)

from ape.manager.simple_manager import SimpleManager, InventoryListener, Listener
from ape.common.requests import PingRequest, AddComponent, StartRequest, InventoryRequest, StopRequest, PerformanceResult, ChangeConfiguration
from ape.component.potato import Potato, PerformOneCycle
from ape.component.potato import Configuration as PotatoConfiguration
from ape.common.messages import  component_id, agent_id, component_type
from time import sleep
import math

class PerformanceListener(Listener):
    def __init__(self):
        self.latest_data = {}
        self.lock = Lock()
    def on_message(self, message):
        if isinstance(message.result, PerformanceResult):
            try:
                self.lock.acquire()
                self.latest_data[message.agent] = message.result
                print 'ops/sec: %f create, %f read, %f update, %f delete' % self.get_rates()
            finally:
                self.lock.release()
    def get_rates(self):
        create = read = update = delete = 0.
        for v in self.latest_data.itervalues():
            create += v.data['create']/v.data['elapsed']
            read += v.data['read']/v.data['elapsed']
            update += v.data['update']/v.data['elapsed']
            delete += v.data['delete']/v.data['elapsed']
        return (create,read,update,delete)

def wait(a):
    raw_input('--- press enter to continue ---')
#    sleep(a)

def main():
    l1 = InventoryListener()
    l2 = PerformanceListener()
    m = SimpleManager()
    m.add_listener(l1)
    m.add_listener(l2)

    # get inventory -- see what agents we have running
    m.send_request(InventoryRequest())
    sleep(5)

    # start component on each agent and let it add documents to db
    components = []
    initial_config = PotatoConfiguration()
    initial_config.read_count = initial_config.update_count = initial_config.delete_count = 0
    initial_config.create_count = 10000
    for agent in l1.inventory.keys():
        print 'adding couch potato for agent: ' + agent
        component_name = 'chip-'+agent
        components.append(component_name)
        component = Potato(component_name, None, initial_config)
        m.send_request(AddComponent(component), agent_filter=agent_id(agent), component_filter=component_id('AGENT'))
        sleep(2) # need at least a little time to let first component register name or second may fail due to race condition
        m.send_request(PerformOneCycle(), agent_filter=agent_id(agent), component_filter=component_id(component_name))

    while len(l2.latest_data)<len(components):
        sleep(1)

    print 'initialization ops/sec: %f create, %f read, %f update, %f delete' % l2.get_rates()

    cycle_config = PotatoConfiguration()
    for component_name in components:
        print 'starting db operations on: ' + component_name
        m.send_request(ChangeConfiguration(cycle_config), component_filter=component_id(component_name))
        m.send_request(StartRequest(), component_filter=component_id(component_name))

    # log results as they arrive for 5 min then stop traffic
    sleep(300)
    m.send_request(StopRequest(), component_filter=component_type(Potato))
    sleep(5)

if __name__ == "__main__":
    main()
