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
#        broker_config = { 'broker_hostname': 'ec2-50-17-108-226.compute-1.amazonaws.com',
#                                    'broker_username': '69B41555-A958-4115-8ED5-3D580B5CF688',
#                                    'broker_password': '4878E506-875F-41DA-B7F5-B9FC7F904EF5' }
        m = SimpleManager(**broker_config)

        l = InventoryListener()
        m.add_listener(l)

        while True:
        # get inventory -- see what agents we have running
            m.send_request(InventoryRequest())
            print '-----------------------------------------------\n\nrequested inventory -- waiting for reply messages'
            sleep(5)

            print 'inventory after nodes have started: '
            show_inventory(l.inventory)
            wait(5)

    finally:
        print 'now stopping nodes'
#        t.stop_nodes()


def show_inventory(i):
    if not i:
        print 'None'
    for key in i.keys():
        print 'agent ' + key + ':'
        print i[key]

if __name__ == "__main__":
    main()
