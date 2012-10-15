"""
base class for end-to-end system test

written as a base class because to express the general outline and flow,
but subclass will provide the actual test details in the perform_test() function
"""
import time

from ape.system.couch import launch_couch, reconnect_couch
from ape.system.rabbit import launch_rabbit, reconnect_rabbit
from ape.system.elasticsearch import launch_elasticsearch, reconnect_elasticsearch
from ape.system.graylog import launch_graylog, reconnect_graylog
from ape.system.containers import launch_containers, reconnect_containers
from ape.manager.simple_manager import SimpleManager, Listener, InventoryListener
from ape.common.requests import AddComponent, InventoryRequest
from ape.common.messages import  component_id
from ape.common.requests import InventoryResult

# simple communication with agents (ping, inventory, etc) will wait at least this long for responses
MIN_WAIT_RESPONSE=30

class SystemTest(object):

    def __init__(self, config):
        """ create test with system configuration """
        self.config = config

    def launch_system(self):
        """ bring up all VMs and applications """
        #
        self.couch = launch_couch(self.config)
        self.rabbit = launch_rabbit(self.config)
        self.es = launch_elasticsearch(self.config)
        self.graylog = launch_graylog(self.config)
        self.wait_for(couch=self.couch, rabbit=self.rabbit, elasticsearch=self.es, graylog=self.graylog)
        #
        self.system = launch_containers(config=self.config, couch=self.couch, rabbit=self.rabbit, graylog=self.graylog, elasticsearch=self.es)
        self.wait_for(pycc=self.system)

        # now system is up and running
        # attach ape manager and listeners
        self._init_manager()

    def reconnect_system(self):
        print '**** reconnect_system'
        self.couch = reconnect_couch(self.config)
        self.rabbit = reconnect_rabbit(self.config)
        self.es = reconnect_elasticsearch(self.config)
        self.graylog = reconnect_graylog(self.config)
        self.system = reconnect_containers(config=self.config, couch=self.couch, rabbit=self.rabbit, graylog=self.graylog, elasticsearch=self.es)
        self._init_manager()

    def start_components(self):
        """ start all components within the applications """
#        init_timer = Timer("initialization")
        self.preload_system(self.config, self.manager, self.system)
#        init_timer.next_step("preload")
        self.devices = self.start_devices(self.config, self.manager, self.system)
#        init_timer.next_step("devices")
        self.transforms = self.start_transforms(self.config, self.manager, self.system, self.devices)
#        init_timer.next_step("transforms")
        self.wait_for(traffic=self.speedometer)
#        init_timer.last_step("flow")
        # now instrument data is passing through the system

    def perform_test(self):
        # IMPLEMENT IN SUBCLASS:
        # do stuff here and measure effect on data throughput.
        # here's the interesting part of the test!
        pass

    def stop_system(self):
        """ shut down applications and VMs """
        self.destroy(pycc=self.system)
        self.destroy(couch=self.couch, rabbit=self.rabbit, graylog=self.graylog, elasticsearch=self.es)

    ############################################################################################

    def _init_manager(self):
        self.manager = self._create_manager()
        self.speedometer = MeasureDataFlow()
        self.manager.add_listener(self.speedometer)
        self.inventory = TimedInventoryListener()
        self.manager.add_listener(self.inventory)

    def _create_manager(self):
#        # TODO: if have specific ape-rabbit config, use it
#        type = self.config.get('ape-rabbit.type')
#        if type:
#            return
        # otherwise, if rabbit server is created by launch plan, query that
        type = self.config.get('rabbit.type')
        if type=='launch-generated':
            return self.system.get_manager()
        # otherwise query rabbit config
        host = self.rabbit.get_hostname()
        user = self.rabbit.get_username()
        pswd = self.rabbit.get_password()
        return SimpleManager(broker_hostname=host, broker_username=user, broker_password=pswd)

    def wait_for(self, couch=None, rabbit=None, graylog=None, elasticsearch=None, pycc=None, traffic=None):
        """ wait until the given resources are up and running, ready to use """
        if couch:
            pass
        if rabbit:
            pass
        if graylog:
            pass
        if pycc:
            pycc.wait_for_containers()
        if traffic:
            pass
        if elasticsearch:
            pass

    ############################################################################################

    def preload_system(self, config, manager, system):
        """ perform DB preload as defined in config file """
        pass

    def start_devices(self, config, manager, system):
        """ start all devices defined in config file """
        pass

    def start_transforms(self, config, manager, system, devices):
        """
        config file will define a series of transforms for each device
        and one more at the end that consumes all data and reports the rate back to our listener
        """
        pass

    ############################################################################################

    def destroy(self, couch=False, rabbit=False, graylog=False, elasticsearch=False, pycc=False):
        pass

        ############################################################################################

    def get_inventory(self):
        """ send inventory request, wait at least 30sec from send or last response, then return inventory """
        start = time.time()
        end = start + MIN_WAIT_RESPONSE

        self.manager.send_request(InventoryRequest(), component_filter=component_id('AGENT'))
        while time.time() < end:
            time.sleep(end-time.time())
            new_end = self.inventory.last_response + MIN_WAIT_RESPONSE
            if new_end>end:
                end = new_end
        return self.inventory.inventory

class MeasureDataFlow(Listener):
    def get_message_rate(self):
        pass

class TimedInventoryListener(Listener):
    def __init__(self):
        self.inventory = {}
        self.last_response = time.time()
    def on_message(self, message):
        if isinstance(message.result, InventoryResult):
            self.last_response = time.time()
            self.inventory[message.agent] = message.result
