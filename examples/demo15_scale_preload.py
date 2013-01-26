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
import time

gevent.monkey.patch_all(aggressive=False)

log = logging.getLogger('demo13')

def _step(msg):
    log.info('[%s] %s', time.ctime(), msg)

def _exists():
    log.info('-----> db exists? %r' % os.path.exists('/Users/jnewbrough/.cloudinitd/cloudinitd-demo13.db'))

def main():
    start_time = time.time()
    log = logging.getLogger('test')
    config = read_test_configuration()
#    _step('config:\n' + pformat(config.as_dict()))
    _step('read config file')
    test = SystemTest(config)
    running = False
    try:
        _step('first see if there is already a running cluster')
        _exists()
        test.reconnect_system()
        procs = test.system.get_process_list()
        import pprint
        pprint.pprint(procs)
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
    launch_time = time.time()
    log.info("launch took %.2f seconds" % (launch_time-start_time))

    if running:
        _step('taking inventory')
        inventory = test.get_inventory()
        inventory_time = time.time()
        _step('inventory: ' + ', '.join(inventory.keys()))
        _step('performing base preload')
        test.init_system()
        preload_time = time.time()
        log.info("preload took %.2f seconds" % (preload_time-launch_time))

        config = test.get_preload_template()
        nrange = test.get_preload_range(config)
        for n in nrange:
            _step("starting device %d"%n)
            test.init_device(config,n)

#        test.start_components()
#        driver_time = time.time()
#        log.info("starting devices took %.2f seconds" % (driver_time-preload_time))
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
