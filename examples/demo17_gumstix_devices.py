"""
ape test to perform capacity testing on gumstix hardware

setup:
- start rabbit, couch on a server
- start container on gumstix and a server
- services on gumstix: instrument_management, observatory_management, process_dispatcher
- all other services on server
"""
import gevent.monkey
from ape.system.system_test import SystemTest
from ape.manager.simple_manager import SimpleManager, InventoryListener, Listener
from ape.system.system_configuration import Configuration
from pprint import pprint, pformat
import logging
import os
import time

gevent.monkey.patch_all(aggressive=False)

log = logging.getLogger('demo15')

def _step(msg):
    log.info('[%s] %s', time.ctime(), msg)

def _rates(data):
    if data:
        min_value = 10000
        max_value = -5
        sum = 0
        for key in data:
            value = 6000/data[key]
            min_value = min(min_value,value)
            max_value = max(max_value,value)
            sum += value
        _step("reporting rates for %d devices, min %f, max %f, avg %f (msgs/min), total %f (msgs/sec)" % (len(data), min_value, max_value, sum/len(data), sum/60))
    else:
        _step("no rates reported yet")

def main():
    start_time = time.time()
    log = logging.getLogger('test')
    config = read_test_configuration()
    #    _step('config:\n' + pformat(config.as_dict()))
    _step('read config file')
    test = SystemTest(config)

    try:
        _step('connecting to agent')
        test.reconnect_system()

        _step('taking inventory')
        inventory = test.get_inventory()
        _step('inventory: ' + ', '.join(inventory.keys()))

        _step('performing base preload')
        preload_start_time = time.time()
        test.init_system()
        preload_time = time.time()
        _step("preload took %.2f seconds" % (preload_time-preload_start_time))

        config = test.get_preload_template()
        nrange = test.get_preload_range(config)
        for n in nrange:
            _step("starting device %d"%n)
            device_begin = time.time()
            test.init_device(config,n, catch_up_frequency=1)
            elapsed = time.time() - device_begin
            _step("completed device %d launch in %f seconds" % (n,elapsed))
            _rates(test.get_message_rates())

        _step('performing test')
        results = test.perform_test()
        _step('*** test completed! ***')
        if results:
            _step('results: ' + str(results))
    except Exception,e:
        log.error('test failed', exc_info=True)
    finally:
        _step('test complete')
        test.stop_system()

def read_test_configuration():
    return Configuration('resources/gumstix-system-launch.yml')

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
