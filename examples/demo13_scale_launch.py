"""
ape test preparing for the scale testing.
want to launch cluster, start transforms, start instruments, monitor results, and disrupt the system
"""
import gevent.monkey
from ape.system.system_test import SystemTest
from ape.system.system_configuration import Configuration
from pprint import pprint, pformat
import logging
import os
import sys

gevent.monkey.patch_all(aggressive=False)

log = logging.getLogger('demo13')

def _step(msg):
    log.info('*** ' + msg)

def _exists():
    log.info('-----> db exists? %r' % os.path.exists('/Users/jnewbrough/.cloudinitd/cloudinitd-demo13.db'))

def main():
    log = logging.getLogger('test')
    config = read_test_configuration()
    _step('config:\n' + pformat(config.as_dict()))
    test = SystemTest(config)
    running = False
    try:
        _step('first see if there is already a running cluster')
        _exists()
        test.reconnect_system()
        running = True
    except:
        log.warn('did not reconnect', exc_info=True)
        _exists()
        _step('failed to connect to running cluster, launching new one instead')
        try:
            test.launch_system()
            running = True
        except Exception,e:
            log.error('test failed', exc_info=True)


    if running:
        _step('taking inventory')
        inventory = test.get_inventory()
        pprint(inventory)
        _step('starting components')
        test.start_components()
        _step('performing test')
        results = test.perform_test()
        if results:
            print 'test results: ' + str(results)
            #test.stop_system()

    _step('test complete')
    os._exit(0)

def read_test_configuration():
    return Configuration('resources/manual-system-launch.yml')

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
