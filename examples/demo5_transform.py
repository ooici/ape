"""
ape sample: transform

creates a data pathway with two producers, a transform using output of both, and a consumer

the two producers are InstrumentSimulators each producing lists of values.
the values are the same (0.1) but the length of the lists differ (1 or 5 values).
the transform adds the values in the list and outputs the sum.
the consumer prints the values it sees, which should alternate between 0.1 and 0.5.
"""

import gevent.monkey
from threading import Lock
import time
from ape.component.transform import TransformComponent
from ape.component.transform import Configuration as TransformConfiguration

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


def wait(a):
    raw_input('--- press enter to continue ---')
#    sleep(a)

sum_values = "output['value'] = sum(input['value'])"

class PerformanceListener(Listener):
    def __init__(self):
        self.latest_data = None
        self.lock = Lock()
    def on_message(self, message):
        if isinstance(message.result, PerformanceResult):
            try:
                self.lock.acquire()
                self.latest_data = message.result
            finally:
                self.lock.release()
    def get_rate(self):
        data = self.latest_data.data if self.latest_data else None
        if data:
            return data['count']/data['elapsed']
        else:
            return 0

def main():
    l1 = InventoryListener()
    m = SimpleManager()
    l2 = PerformanceListener()
    m.add_listener(l1)
    m.add_listener(l2)

    # get inventory -- see what agents we have running
    m.send_request(InventoryRequest())
    sleep(5)

    count = 0
    for agent in l1.inventory.keys():
        # producer --> transform --> consumer
        print 'adding components for agent: ' + agent

        count += 1
        ext = str(count)
        instrument1_dataproduct_name = 'test-stream1-' + ext
        instrument2_dataproduct_name = 'test-stream2-' + ext
        transform_dataproduct_name = 'test-stream3-' + ext

        producer1_component_name = 'pro1-'+ext
        producer2_component_name = 'pro2-'+ext
        transform_component_name = 'tran-'+ext

        print 'adding producer'
        producer1_config = InstrumentConfiguration(instrument1_dataproduct_name, 2, instrument_configuration=1,
            persist_product=False, report_timing=True, timing_rate=5000)
        producer1 = InstrumentSimulator(producer1_component_name, None, producer1_config)
        m.send_request(AddComponent(producer1), agent_filter=agent_id(agent), component_filter=component_id('AGENT'))

        producer2_config = InstrumentConfiguration(instrument2_dataproduct_name, 2, instrument_configuration=5,
            persist_product=False, report_timing=True, timing_rate=5000)
        producer2 = InstrumentSimulator(producer2_component_name, None, producer2_config)
        m.send_request(AddComponent(producer2), agent_filter=agent_id(agent), component_filter=component_id('AGENT'))

        print 'adding transform'
        transform_config = TransformConfiguration(transform_function=sum_values) #(lambda input: dict(value=sum(input['value']))))
        transform_config.add_input(instrument1_dataproduct_name)
        transform_config.add_input(instrument2_dataproduct_name)
        transform_config.add_output(transform_dataproduct_name)
        transform_config.add_output_field('value')
        transform_config.stats_interval = 10
        transform_config.report_stats = True
        transform = TransformComponent(transform_component_name, None, transform_config)
#        print 'outputs: ' + repr(transform.configuration.outputs)
        m.send_request(AddComponent(transform), agent_filter=agent_id(agent), component_filter=component_id('AGENT'))

        print 'adding consumer'
        consumer_component_name = 'con-'+ext
        consumer = DataProductConsumer(consumer_component_name, None, ConsumerConfiguration(transform_dataproduct_name, log_value=True))
        m.send_request(AddComponent(consumer), agent_filter=agent_id(agent), component_filter=component_id('AGENT'))

        print 'starting data flow'
        m.send_request(StartRequest(), agent_filter=agent_id(agent), component_filter=component_id(consumer_component_name))
        m.send_request(StartRequest(), agent_filter=agent_id(agent), component_filter=component_id(transform_component_name))
        m.send_request(StartRequest(), agent_filter=agent_id(agent), component_filter=component_id(producer1_component_name))
        m.send_request(StartRequest(), agent_filter=agent_id(agent), component_filter=component_id(producer2_component_name))
        sleep(2) # need at least a little time to let first component register name or second may fail due to race condition

    # log results as they arrive for a while
    wait_time=90
    end_time = time.time()+wait_time
    wait_interval=5
    while time.time()<end_time:
        print 'messages per sec: %f'%l2.get_rate()
        sleep(wait_interval)

    # then stop traffic
    m.send_request(StopRequest(), component_filter=component_type(InstrumentSimulator))
    print 'data producer stopped'
    sleep(5)
#    wait(2)

if __name__ == "__main__":
    main()
