import gevent.monkey

gevent.monkey.patch_all(aggressive=False)

from ape.manager.simple_manager import SimpleManager
from ape.common.requests import PingRequest, AddComponent, StartRequest
from ape.component.instrument_simulator import InstrumentSimulator
from ape.component.instrument_simulator import Configuration as InstrumentConfiguration
from ape.component.consumer import DataProductConsumer
from ape.component.consumer import Configuration as ConsumerConfiguration
from ape.common.messages import  component_id
from time import sleep

def wait(a):
    raw_input('--- press enter to continue ---')
#    sleep(a)

def main():
    m = SimpleManager()

    data_product_name = 'test-stream-1'
    producer = InstrumentSimulator('pro1', None, InstrumentConfiguration(data_product_name, 0.001))
    m.send_request(AddComponent(producer), component_filter=component_id('AGENT'))
    print 'instrument created'

    consumer = DataProductConsumer('con1', None, ConsumerConfiguration(data_product_name))
    m.send_request(AddComponent(consumer), component_filter=component_id('AGENT'))

    m.send_request(StartRequest(), component_filter=component_id('con1'))
    m.send_request(StartRequest(), component_filter=component_id('pro1'))
    sleep(10)
    sleep(10)
    wait(10)

if __name__ == "__main__":
    main()