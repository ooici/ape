"""
ape sample: publish/subscribe

create an InstrumentSimulator component which registers a new data product and creates messages at a specified rate,
and a DataProductConsumer component that receives these messages and discards (optionally prints) them.
although the pair of ape components are created on each agent found,
the actual processes are requested from the system and could be launched in a different container entirely.
"""
from sys import argv
from threading import Lock
from ape.manager.sunny import ScriptedTroop

import gevent.monkey

gevent.monkey.patch_all(aggressive=False)

from ape.manager.simple_manager import SimpleManager, InventoryListener, Listener
from ape.common.requests import PingRequest, AddComponent, StartRequest, InventoryRequest, StopRequest, PerformanceResult, ChangeConfiguration
from ape.component.potato import Potato, PerformOneCycle
from ape.component.potato import Configuration as PotatoConfiguration
from ape.common.messages import  component_id, agent_id, component_type
from time import sleep, time
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
#                print 'ops/sec: %f create, %f read, %f update, %f delete, %d nodes' % self.get_rates()
            finally:
                self.lock.release()
    def get_rates(self):
        create = read = update = delete = 0.
        nodes = len(self.latest_data)
        for v in self.latest_data.itervalues():
            create += v.data['create']/v.data['elapsed']
            read += v.data['read']/v.data['elapsed']
            update += v.data['update']/v.data['elapsed']
            delete += v.data['delete']/v.data['elapsed']
        return create,read,update,delete,nodes

def wait(a):
    raw_input('--- press enter to continue ---')
#    sleep(a)

_CHARSET="-0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ_abcdefghijklmnopqrstuvwxyz"

def main():
    if len(argv):
        update_count=int(argv[1])
        nodes=int(argv[2])
        print 'parsed arguments -- update count: ' + str(update_count) + ' expected nodes: ' + str(nodes)
    else:
        raise Exception('missing arguments')

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

    # start component on each agent and let it add documents to db
    total_documents_target = 1000000
    documents_per_iteration = 20000
    components = []
    initial_config = PotatoConfiguration()
    initial_config.read_count = initial_config.update_count = initial_config.delete_count = 0
    initial_config.create_count = int(documents_per_iteration/nodes)
    agent_list = [id for id in l1.inventory.keys()]
    salt = {}
    count = 0
    for agent in agent_list:
        print 'adding couch potato for agent: ' + agent
        component_name = 'chip-'+agent
        components.append(component_name)

        # give each agent unique salt for id generation
        salt[agent] = _CHARSET[count]
        count+=1
        initial_config.id_salt = ['-','-',salt[agent]]

        component = Potato(component_name, None, initial_config)
        m.send_request(AddComponent(component), agent_filter=agent_id(agent), component_filter=component_id('AGENT'))
        sleep(2) # need at least a little time to let first component register name or second may fail due to race condition

    total_start = time()
    for x in xrange(total_documents_target/documents_per_iteration):
        l2.latest_data.clear()
        m.send_request(PerformOneCycle(), component_filter=component_type(Potato))
        iteration_start = time()
        print 'waiting for containers to finish creating initial documents in db'
        while len(l2.latest_data)<len(components):
            sleep(5)
        elapsed = time() - iteration_start
        print 'created %d docs in %f secs: %f ops/sec' % (documents_per_iteration, elapsed, documents_per_iteration/elapsed)
    elapsed = time() - total_start
    print 'DONE: created %d docs in %f secs' % (total_documents_target, elapsed)



if __name__ == "__main__":
    main()
