"""
ape sample: publish/subscribe

create an InstrumentSimulator component which registers a new data product and creates messages at a specified rate,
and a DataProductConsumer component that receives these messages and discards (optionally prints) them.
although the pair of ape components are created on each agent found,
the actual processes are requested from the system and could be launched in a different container entirely.
"""

import gevent.monkey

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

class PerformanceListener(Listener):
    def __init__(self):
        self.latest_data = {}
        self.known_components = []
    def add_component(self, component_id):
        self.known_components.append(component_id)
    def on_message(self, message):
        if isinstance(message.result, PerformanceResult):
            self.latest_data[message.agent] = message.result
            print 'update: rate=' + str(self.get_rate()) + ' msgs/sec'
    def get_rate(self):
        iterations_per_second = 0.
        for v in self.latest_data.itervalues():
            iterations_per_second += v.data['count']/v.data['time']
        return iterations_per_second

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

    count = 0
    for agent in l1.inventory.keys():
        print 'adding producer/consumer for agent: ' + agent
        count += 1
        ext = str(count)
        data_product_name = 'test-stream-' + ext
        producer_component_name = 'pro-'+ext
        consumer_component_name = 'con-'+ext

        producer_config = InstrumentConfiguration(data_product_name, 0, instrument_configuration=100,
                                    sleep_even_zero=False,
                                    persist_product=False, report_timing=True, timing_rate=5000)
        producer = InstrumentSimulator(producer_component_name, None, producer_config)
        consumer = DataProductConsumer(consumer_component_name, None, ConsumerConfiguration(data_product_name, log_value=False))

        m.send_request(AddComponent(producer), agent_filter=agent_id(agent), component_filter=component_id('AGENT'))
        m.send_request(AddComponent(consumer), agent_filter=agent_id(agent), component_filter=component_id('AGENT'))
        m.send_request(StartRequest(), agent_filter=agent_id(agent), component_filter=component_id(consumer_component_name))
        m.send_request(StartRequest(), agent_filter=agent_id(agent), component_filter=component_id(producer_component_name))
        sleep(2) # need at least a little time to let first component register name or second may fail due to race condition

    # log results as they arrive for 5 min then stop traffic
    sleep(300)
    m.send_request(StopRequest(), component_filter=component_type(InstrumentSimulator))
    sleep(5)
if __name__ == "__main__":
    main()
