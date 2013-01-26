"""
hack -- using scale_test configuration but perform locally

intended to perform a faster system start so i can test the new logging transform component
using the scale test configuration
without all the nimbus launch overhead

--> evenaully should change the scale test framework to allow local execution
"""

import time
import logging
import gevent.monkey
gevent.monkey.patch_all(aggressive=False)
from ape.manager.simple_manager import SimpleManager, Listener
from ape.component.preloader import Preloader, PerformPreload, NotifyPreloadComplete, PathConfiguration, TemplateConfiguration
from ape.common.requests import PingRequest, AddComponent
from ape.common.messages import  component_id
from ion.processes.bootstrap.ion_loader import TESTED_DOC
from ape.system.system_test import SystemTest
from ape.system.system_configuration import Configuration

log = logging.getLogger('demo16')

def _step(msg):
    log.info('*** ' + msg)

class PreloadListener(Listener):
    results = {}
    def on_message(self, message):
        if isinstance(message.result, NotifyPreloadComplete):
            self.results[message.result.id] = message.result

    def clear_result(self, id):
        del self.results[id]
    def wait_for_result(self, id):
        while id not in self.results:
            time.sleep(2)
        return self.results[id]

def main():
    config = Configuration('resources/manual-system-launch.yml')
    test = SystemTest(config)
    try:
        test.reconnect_system()
    except:
        pass ## will fail to connect to cloudinitd, but should reconnect rabbit anyway

    inventory = test.get_inventory()
    inventory_time = time.time()
    _step('inventory: ' + ', '.join(inventory.keys()))

    _step('performing base preload')
    test.init_system()

    config = test.get_preload_template()
    nrange = test.get_preload_range(config)
    for n in nrange:
        _step("starting device %d"%n)
        test.init_device(config,n)
    _step('all done')

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
