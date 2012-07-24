import gevent.monkey
from ape.manager.troop import Troop

gevent.monkey.patch_all(aggressive=False)

from ape.manager.simple_manager import SimpleManager, InventoryListener, Listener
from ape.common.requests import InventoryRequest
from time import sleep, strftime
from numpy import array, zeros

def wait(a):
    raw_input('--- press enter to continue ---')

def main():
    print 'defining a launch plan'
    t = Troop(clobber=True)
    t.configure('resources/one-container-ec2.trp')
    t.create_launch_plan()
    print 'created a launch plan with %d containers' % t.get_container_count()

    # start cloudinitd launch
    print '''NOTICE: an EC2 launch takes about 20min to start the first pycc instance
If interrupted, make sure to stop EC2 instances with the command: cloudinitd terminate %s

now starting launch: %s
-----------------------------------------------''' % (t.launch_name, strftime('%l:%M'))

    try:
        t.start_nodes()
        print '-----------------------------------------------\n\completed launch: %s' % strftime('%l:%M')

        # get manager configured to use rabbitMQ started by launch plan
        m = t.get_manager()

        l = InventoryListener()
        m.add_listener(l)

        keep_waiting = True
        while keep_waiting:
            # shouldn't need to keep requesting each time,
            # but first request could be lost if agent had not yet connected to rabbitmq
            m.send_request(InventoryRequest())
            sleep(5)
            if l.inventory:
                show_inventory(l.inventory)
                keep_waiting = False
            else:
                sleep(10)

    finally:
        print 'now stopping nodes'
        try:
            m.close()
        except:
            print 'failed to close manager connection'
        t.stop_nodes()


def show_inventory(i):
    if not i:
        print 'None'
    for key in i.keys():
        print 'agent ' + key + ':'
        print i[key]

if __name__ == "__main__":
    main()
