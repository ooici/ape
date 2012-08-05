"""
broker load test program

uses instrument producer and no-op consumer to test data granule throughput.
creates one producer/consumer pair per agent and reports cumulative rate for all consumers.
takes command-line arguments to control #bytes data per granule (excluding granule overhead),
and number of agents to expect (waits until all have sent inventory before launching components).
"""

from threading import Lock
from ape.component.consumer import DataProductConsumer
from ape.component.instrument_simulator import InstrumentSimulator
from ape.manager.sunny import ScriptedTroop
import gevent.monkey
from ape.manager.troop import Troop
from sys import argv

gevent.monkey.patch_all(aggressive=False)

from ape.manager.simple_manager import SimpleManager, InventoryListener, Listener
from ape.common.requests import InventoryRequest, PerformanceResult
from time import sleep, strftime
from ape.component.instrument_simulator import Configuration as InstrumentConfiguration
from ape.component.consumer import Configuration as ConsumerConfiguration

from ape.common.requests import PingRequest, AddComponent, StartRequest, InventoryRequest, StopRequest, PerformanceResult
from ape.common.messages import  component_id, agent_id, component_type

def wait(a):
#    raw_input('--- press enter to continue ---')
    sleep(2)


class PerformanceListener(Listener):
    def __init__(self):
        self.latest_data = {}
        self.known_components = []
        self.lock = Lock()
    def add_component(self, component_id):
        self.known_components.append(component_id)
    def on_message(self, message):
        if isinstance(message.result, PerformanceResult):
            self.lock.acquire()
            try:
                self.latest_data[message.agent] = message.result
                count = len(self.latest_data.keys())
                rate = self.get_rate()
            finally:
                self.lock.release()
            print 'update: rate=' + str(rate) + ' msgs/sec with ' + str(count) + ' producers'
    def get_rate(self):
        iterations_per_second = 0.
        for v in self.latest_data.itervalues():
            iterations_per_second += v.data['count']/v.data['time']
        return iterations_per_second



def main():
    if len(argv):
        bytes=int(argv[1])
        nodes=int(argv[2])
        print 'parsed arguments -- sending messages size: ' + str(bytes) + ' expecting nodes: ' + str(nodes)
    else:
        bytes=1
        nodes=None

    print 'defining a launch plan'
    t = ScriptedTroop(clobber=True)
    t.configure('resources/multiple-containers-ec2.trp')
    t.create_launch_plan()
    print 'created a launch plan with %d containers' % t.get_container_count()

    print '-------\nstarting launch (this will take a while)'
#    t.start_nodes()
    print 'launch completed!\n-------'

    m = t.get_manager()

    l1 = InventoryListener()
    l2 = PerformanceListener()
    m.add_listener(l1)
    m.add_listener(l2)

    # get inventory -- see what agents we have running
    m.send_request(InventoryRequest(), component_filter=component_id('AGENT'))
    sleep(5)
    while nodes and len(l1.inventory)<nodes:
        print 'only have %d nodes so far, waiting for more...'%len(l1.inventory)
        m.send_request(InventoryRequest(), component_filter=component_id('AGENT'))
        sleep(5)

    pubsub_same_host = False
    count = 0
    producer_names = []
    previous_consumer = None
    agents = sorted(l1.inventory.keys())
    for agent in agents:
        print 'adding producer/consumer for agent: ' + agent
        count += 1
        ext = str(count)
        data_product_name = 'test-stream-' + ext
        producer_component_name = 'pro-'+ext
        consumer_component_name = 'con-'+ext
        producer_names.append((agent,producer_component_name))

        producer_config = InstrumentConfiguration(data_product_name, 0, instrument_configuration=bytes,
            sleep_even_zero=False,
            persist_product=False, report_timing=True, timing_rate=1000)
        producer = InstrumentSimulator(producer_component_name, None, producer_config)
        consumer = DataProductConsumer(consumer_component_name, None, ConsumerConfiguration(data_product_name, log_value=False))

        m.send_request(AddComponent(producer), agent_filter=agent_id(agent), component_filter=component_id('AGENT'))
        wait('wait for producer to register before starting consumer (press ENTER): ')

        if pubsub_same_host:
            m.send_request(AddComponent(consumer), agent_filter=agent_id(agent), component_filter=component_id('AGENT'))
            m.send_request(StartRequest(), agent_filter=agent_id(agent), component_filter=component_id(consumer_component_name))
        else:
            ### if agents are A, B, C, ...
            # put producer on A and consumer on B; then producer on B and consumer on C; etc
            if previous_consumer:
                m.send_request(AddComponent(previous_consumer), agent_filter=agent_id(agent), component_filter=component_id('AGENT'))
                m.send_request(StartRequest(), agent_filter=agent_id(agent), component_filter=component_id(previous_component_name))
            previous_consumer = consumer
            previous_component_name = consumer_component_name

    if not pubsub_same_host:
        first_agent = agents[0]
        m.send_request(AddComponent(previous_consumer), agent_filter=agent_id(first_agent), component_filter=component_id('AGENT'))
        m.send_request(StartRequest(), agent_filter=agent_id(first_agent), component_filter=component_id(previous_component_name))


    for agent,component in producer_names:
        m.send_request(StartRequest(), agent_filter=agent_id(agent), component_filter=component_id(component))

    # log results as they arrive for 5 min then stop traffic
    print 'producers/consumers running for 5 min'
    sleep(300)

    print 'shutting down'
    m.send_request(StopRequest(), component_filter=component_type(InstrumentSimulator))
    print 'stopped producers'
    sleep(5)
    m.send_request(StopRequest(), component_filter=component_type(DataProductConsumer))
    print 'stopped consumers'
    sleep(5)
    m.close()
    print 'closed manager'


def show_inventory(i):
    print '----------------------'
    if not i:
        print 'None'
    for key in i.keys():
        print 'agent ' + key + ':'
        print i[key]

if __name__ == "__main__":
    main()
