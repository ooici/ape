import unittest
from ape.system.system_configuration import Configuration
from ape.system.containers import Containers
from ape.manager.simple_manager import InventoryListener
import time
from ape.common.requests import InventoryRequest
from ape.common.messages import component_id
from ape.system.system_test import SystemTest
class TestCreateLaunchPlan(unittest.TestCase):
    def test_launch(self):
        subject = SystemTest(Configuration('test/src/system/system-manual.yml'))
        subject.launch_system()

        print 'getting manager...'
        manager = subject.create_manager()
        l = InventoryListener()
        manager.add_listener(l)
        print 'sending inventory request...'
        manager.send_request(InventoryRequest(), component_filter=component_id('AGENT'))
        time.sleep(30)
        print 'inventory: '+ repr(l)
        print 'inventory: '+ repr(l.inventory)
        self.show_inventory()

    def show_inventory(i):
        for key in i.keys():
            print 'agent ' + key + ':'
            print i[key]

if __name__ == '__main__':
    unittest.main()