import unittest
from ape.system.system_configuration import Configuration
from ape.system.containers import Containers
from ape.manager.simple_manager import InventoryListener
import time
from ape.common.requests import InventoryRequest
from ape.common.messages import component_id

class TestCreateLaunchPlan(unittest.TestCase):
    def test_parse_config(self):
        config = Configuration('test/src/system/system-manual.yml')
        subject = Containers(config)
        subject.create_launch_plan()

#        print 'launching plan...'
#        subject.launch_containers()
#        print 'now waiting for launch plan to complete...'
#        subject.wait_for_containers()
#
#        print 'getting manager...'
#        manager = subject.get_manager()
#        l = InventoryListener()
#        manager.add_listener(l)
#        print 'sending inventory request...'
#        manager.send_request(InventoryRequest(), component_filter=component_id('AGENT'))
#        time.sleep(30)
#        print 'inventory: '+ repr(l)
#        print 'inventory: '+ repr(l.inventory)
#        self.show_inventory(l.inventory)

    def show_inventory(i):
        for key in i.keys():
            print 'agent ' + key + ':'
            print i[key]

if __name__ == '__main__':
    unittest.main()