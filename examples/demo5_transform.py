import gevent.monkey
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

#def sum_values(input):
#    return { 'value': sum(input['value']) }
sum_values = "output = { 'value': sum(input['value']) }"

def main():
    l1 = InventoryListener()
    m = SimpleManager()
    m.add_listener(l1)

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

    # log results as they arrive for 5 min then stop traffic
    sleep(30)
    m.send_request(StopRequest(), component_filter=component_type(InstrumentSimulator))
    print 'data producer stopped'
    sleep(5)
#    wait(2)

if __name__ == "__main__":
    main()
