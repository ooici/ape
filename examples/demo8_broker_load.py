""" THIS IS NOT READY TO RUN

    but by writing the code to do the proper broker load test, I'm hoping to flesh out what additional work needs to be done to the troop
"""

from logging import DEBUG
from ape.common.types import ApeException
import gevent.monkey
from ape.common.messages import agent_id, component_id, component_type
from ape.manager.troop import Troop
from ape.component.instrument_simulator import InstrumentSimulator
from ape.component.instrument_simulator import Configuration as InstrumentConfiguration
from ape.component.consumer import DataProductConsumer
from ape.component.consumer import Configuration as ConsumerConfiguration

gevent.monkey.patch_all(aggressive=False)
from pyon.util.log import log

from ape.manager.simple_manager import SimpleManager, InventoryListener, Listener
from ape.common.requests import InventoryRequest, PerformanceResult, AddComponent, StartRequest, StopRequest, PingResult
from time import sleep

def wait(a):
    raw_input('--- press enter to continue ---')

GRANULE_SIZE_FLOATS=10
AGENT_CONTAINERS=4                # how many containers to start (complete guess at this point!)
GIVE_UP_AFTER_DECREASING_NODES=5   # after this many nodes in a row not setting a new max, give up, we found it already
TARGET_RATE_PORTION_OF_MAX=0.8

# NOTE: 25 containers (+2 more), 1-2 min per component (more after reaching capacity) -- likely 2+ hours to run test.
# will cost about $5 each run on EC2

# TODO: when adding more nodes does not increase capacity, stop test

def main():


#log.setLevel(DEBUG)
    t = Troop(clobber=True)
    t.configure('resources/one-container-ec2.trp')
    t.set_name('load-test')
    print 'before:\nconfig: %s\ntypes: %s' % (repr(t.configuration), repr(t.node_types))
    t.change_count('container-with-services', AGENT_CONTAINERS)
    print 'after:\nconfig: %s\ntypes: %s' % (repr(t.configuration), repr(t.node_types))
    t.create_launch_plan()

    m = None
    try:
        log.info('now starting nodes\n\n-----------------------------------------------') # bracket STDOUT of cloudinitd
        t.start_nodes()
        log.info('\n-----------------------------------------------\n\n')

        i_listener = InventoryListener()
        p_listener = PerformanceListener()
        m = t.get_manager()
        m.add_listener(i_listener)
        m.add_listener(p_listener)

        # TODO: troop should start agent with configuration setting for name of container type,
        #       so here we call can target only the non-service containers:
        # m.send_request(InventoryRequest(), agent_filter=container_type('container-without-services'))
        #       without this ability, we run producer/consumer on container with services which has other overhead
        log.info('requested inventory -- waiting for reply messages')
        max_wait=9999999999 #sec
        for n in xrange(max_wait/30):
            m.send_request(InventoryRequest(), component_filter=component_id('AGENT'))
            sleep(30)
            reply_count = len(i_listener.inventory)
            log.info('requested %d containers, have replies from %d containers' % (AGENT_CONTAINERS, reply_count))
            if AGENT_CONTAINERS<reply_count:
                log.warn('have more containers than requested?')
                break
            elif AGENT_CONTAINERS==reply_count:
                break
        log.debug('found %d containers', len(i_listener.inventory))
        if len(i_listener.inventory)<AGENT_CONTAINERS:
            raise ApeException('failed to start requested number of containers')

        # determine reasonable rate for nodes
        any_agent = i_listener.inventory.keys()[0]
        max_node_rate = find_node_max(m, p_listener, any_agent, 1000)
        log.debug('max rate %.2e', max_node_rate)

        if not max_node_rate:
            raise ApeException('failed to get max rate from first VM')
        target_node_rate = max_node_rate * TARGET_RATE_PORTION_OF_MAX
        log.debug('max rate for one node is %.2f msgs/sec, target rate is %.2f msgs/sec', max_node_rate, target_node_rate)

        # create producers/consumers on remaining agents
        index=2
        max_broker_rate = max_node_rate
        max_index=1
        for agent in i_listener.inventory.keys()[1:]:
            add_node_traffic(m, p_listener, agent, target_node_rate, 'agent%d'%index)

            # make sure have fresh measurement from each node
            # b/c node that was going faster may have slowed down
            # now that latest node has pushed broker to saturation
            sleep(10)
            p_listener.clear()
            for n in xrange(60/5):
                if len(p_listener.latest_data)>=index:
                    break
                sleep(5)
            measured_broker_rate = p_listener.get_rate()
            log.debug('broker passing %.2e msgs/sec with %d producers', measured_broker_rate, index)
            if measured_broker_rate>max_broker_rate:
                max_broker_rate = measured_broker_rate
                max_index = index
            index+=1
        log.info('max rate was %.2e msgs/sec with %d producers', max_broker_rate, max_index)

    finally:
        log.info('now stopping nodes')
        if m:
            m.send_request(StopRequest(), component_filter=component_type(InstrumentSimulator))
            m.send_request(StopRequest(), component_filter=component_type(DataProductConsumer))
            m.close()
#        t.stop_nodes()

def find_node_max(manager, listener, agent, report_rate):
    """ send messages at max rate on one node """
    config = InstrumentConfiguration('node-max-data-product', 0, instrument_configuration=GRANULE_SIZE_FLOATS, report_timing=True, log_timing=True, timing_rate=report_rate)
    producer = InstrumentSimulator('node-max-producer', None, config)
    consumer = DataProductConsumer('node-max-consumer', None, ConsumerConfiguration('node-max-data-product', log_value=False))
    manager.send_request(AddComponent(producer), agent_filter=agent_id(agent), component_filter=component_id('AGENT'))
    manager.send_request(AddComponent(consumer), agent_filter=agent_id(agent), component_filter=component_id('AGENT'))
    manager.send_request(StartRequest(), agent_filter=agent_id(agent), component_filter=component_id('node-max-consumer'))
    manager.send_request(StartRequest(), agent_filter=agent_id(agent), component_filter=component_id('node-max-producer'))

    log.debug('started producer/consumer on %s, waiting for performance measurement', agent)
    listener.clear()
    max_wait=300 # 5min
    for n in xrange(max_wait/5):
        sleep(5)
        if listener.get_rate()>0:
            break
#    manager.send_request(StopRequest(), agent_filter=agent_id(agent), component_filter=component_id('node-max-consumer'))
#    manager.send_request(StopRequest(), agent_filter=agent_id(agent), component_filter=component_id('node-max-producer'))
    return listener.get_rate()

def add_node_traffic(manager, listener, agent, rate, name):
    """ add producer/consumer on node and make sure message rate is close to target """
    # start producer/consumer
    config = InstrumentConfiguration(name + '-data-product', rate, instrument_configuration=GRANULE_SIZE_FLOATS, log_timing=False, timing_rate=rate*10)
    producer = InstrumentSimulator(name + '-producer', None, config)
    consumer = DataProductConsumer(name + '-consumer', None, ConsumerConfiguration(name + '-data-product', log_value=False))
    manager.send_request(AddComponent(producer), agent_filter=agent_id(agent), component_filter=component_id('AGENT'))
    manager.send_request(AddComponent(consumer), agent_filter=agent_id(agent), component_filter=component_id('AGENT'))
    manager.send_request(StartRequest(), agent_filter=agent_id(agent), component_filter=component_id(name + '-consumer'))
    manager.send_request(StartRequest(), agent_filter=agent_id(agent), component_filter=component_id(name + '-producer'))
    log.debug('started producer/consumer on %s, waiting for message rate', agent)
    # measure performance
    max_wait=600 # 10min
    measured_rate=0
    for n in xrange(max_wait/5):
        sleep(5)
        measured_rate = listener.get_node_rate(name + '-producer')
        if measured_rate>0:
                break
    log.debug('agent %s message rate is %.2e', agent, measured_rate)
    return measured_rate

class PerformanceListener(Listener):
    def __init__(self):
        self.latest_data = {}
    def clear(self, node=None):
        if node:
            del self.latest_data[node]
        else:
            self.latest_data.clear()
    def on_message(self, message):
        if isinstance(message.result, PerformanceResult):
            self.latest_data[message.agent] = message.result
            log.debug('update from %s: rate=%.2e msgs/sec', message.agent, self.get_node_rate(message.agent))
    def get_rate(self):
        iterations_per_second = 0.
        for v in self.latest_data.itervalues():
            iterations_per_second += v.data['count']/v.data['time']
        return iterations_per_second
    def get_node_rate(self, agent):
        data = self.latest_data[agent].data
        return data['count']/data['time']

class PingListener(Listener):
    def __init__(self):
        self.responses = []
    def clear(self):
        self.responses = []
    def on_message(self, message):
        if isinstance(message.result, PingResult):
            self.responses.append(message.agent)
            log.debug('%s is alive', message.agent)

def show_inventory(i):
    if not i:
        log.info('None')
    for key in i.keys():
        log.info('agent ' + key + ':' + i[key])

if __name__ == "__main__":
    main()
