"""
instrument controller component

capable of creating, initializing and managing access to an instrument
"""
from ape.common.types import ApeComponent, ApeException
from ape.component.gateway_client import ServiceApi

class Instrument(object):
    """ defines a specific instrument to be managed """
    def __init__(self, name):
        self.name = name

class InstrumentController(ApeComponent):

    def create_instrument(self, instrument):
        """ add all entries into resource registry """
        # TODO: for now use preload to initialize instrument entries in registry

    def list_instruments(self):
        """ perform lookup used by ion-ux to generate list of devices """
        return ServiceApi.find_by_resource_type('InstrumentDevice')

    def find_instrument(self, name):
        """ determine id of device with given name """
        instruments = self.list_instruments()
        instrument_attributes = None
        for i in instruments:
            if i['name']==name:
                if instrument_attributes:
                    raise ApeException('found two instruments with name: ' + name)
                instrument_attributes = i
        if not instrument_attributes:
            raise ApeException('could not find instrument with name: ' + name)
        return instrument_attributes['_id']

    def lookup_instrument(self, device_id):
        """ perform service gateway lookups ordinarily performed by ion-ux to load a device """
        instrument = ServiceApi.find_instrument(device_id)

    def start_device(self, device_id):
        """ start necessary drivers and agents for instrument """
        response = ServiceApi.instrument_agent_start(device_id)
        # if response is success...
        response = ServiceApi.instrument_execute_agent(device_id, 'initialize')
        # if response is success...
        response = ServiceApi.instrument_execute_agent(device_id, 'go_active')
        # if response is success...
        response = ServiceApi.instrument_execute_agent(device_id, 'go_streaming')

    def stop_device(self, instrument):
        """ stop driver/agent processes """
