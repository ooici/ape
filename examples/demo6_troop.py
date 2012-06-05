import gevent.monkey
from ape.component.transform import TransformComponent
from ape.component.transform import Configuration as TransformConfiguration
from ape.manager.troop import Troop

gevent.monkey.patch_all(aggressive=False)

from ape.manager.simple_manager import SimpleManager, InventoryListener, Listener
from ape.common.requests import InventoryRequest
from time import sleep
from numpy import array, zeros

def wait(a):
    raw_input('--- press enter to continue ---')

def main():
    print 'defining a launch plan'
    t = Troop(clobber=True)
    t.configure('resources/three-containers.trp')
    t.create_launch_plan()
    print 'created a launch plan with %d containers' % t.get_container_count()
    print 'now starting nodes\n\n-----------------------------------------------'

    try:
        t.start_nodes()

        broker_config = t.get_nodes_broker()
        m = SimpleManager(**broker_config)

        l = InventoryListener()
        m.add_listener(l)

        # get inventory -- see what agents we have running
        m.send_request(InventoryRequest())
        print '-----------------------------------------------\n\nrequested inventory -- waiting for reply messages'
        sleep(30)

        print 'inventory after nodes have started: '
        show_inventory(l.inventory)

    finally:
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
