import gevent.monkey

gevent.monkey.patch_all(aggressive=False)

from ape.manager.simple_manager import SimpleManager
from ape.common.requests import PingRequest, AddComponent, StartRequest, InventoryRequest
from ape.component.instrument_simulator import InstrumentSimulator
from ape.component.instrument_simulator import Configuration as InstrumentConfiguration
from ape.component.consumer import DataProductConsumer
from ape.component.consumer import Configuration as ConsumerConfiguration
from ape.common.messages import  component_id, agent_id, component_type
from time import sleep

def wait(a):
    raw_input('--- press enter to continue ---')
#    sleep(a)

def main():
    m = SimpleManager()

    # get inventory -- see what agents we have running
    m.send_request(InventoryRequest())
    sleep(5)

    count = 0
    for agent in m.inventory.keys():
        print 'adding producer/consumer for agent: ' + agent
        count += 1
        ext = str(count)
        data_product_name = 'test-stream-' + ext
        producer_component_name = 'pro-'+ext
        consumer_component_name = 'con-'+ext

        producer_config = InstrumentConfiguration(data_product_name, 0, persist_product=False,
                                    sleep_even_zero=False,
                                    log_timing=True, timing_rate=10000)
        producer = InstrumentSimulator(producer_component_name, None, producer_config)
        consumer = DataProductConsumer(consumer_component_name, None, ConsumerConfiguration(data_product_name))

        m.send_request(AddComponent(producer), agent_filter=agent_id(agent), component_filter=component_id('AGENT'))
        m.send_request(AddComponent(consumer), agent_filter=agent_id(agent), component_filter=component_id('AGENT'))
        m.send_request(StartRequest(), agent_filter=agent_id(agent), component_filter=component_id(consumer_component_name))
        m.send_request(StartRequest(), agent_filter=agent_id(agent), component_filter=component_id(producer_component_name))
        sleep(2) # need at least a little time to let first component register name or second may fail due to race condition
        wait(10)

#    sleep(60)
#    m.send_request(StopRequest(), component_filter=component_type(InstrumentSimulator))
if __name__ == "__main__":
    main()