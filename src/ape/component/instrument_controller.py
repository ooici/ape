"""
instrument controller component

capable of creating, initializing and managing access to an instrument
"""
from ape.common.requests import OperationResult, getResult, ChangeConfiguration
from ape.common.types import ApeComponent, ApeException, ApeRequest
from ape.component.gateway_client import ServiceApi
from pyon.public import PRED, RT
from interface.services.coi.iresource_registry_service import ResourceRegistryServiceClient
from pyon.core.exception import IonException
import time
from ooi.logging import log

class GetInstrumentNames(ApeRequest): pass
class GetInstrumentId(ApeRequest):
    def __init__(self, name):
        self.name = name
class StartDevice(ApeRequest):
    def __init__(self, id):
        self.id = id
class GetDataProduct(ApeRequest):
    def __init__(self, id):
        self.id = id

class InstrumentController(ApeComponent):
    _resource_registry = None

    def perform_action(self, request):
        if isinstance(request, GetInstrumentNames):
            self.report(getResult(self.list_instruments))
        elif isinstance(request, GetInstrumentId):
            out = getResult(self.find_instrument, request.name)
            print 'sending report: ' + repr(out)
            self.report(out)
        elif isinstance(request, StartDevice):
            self.start_device(request.id)
        elif isinstance(request, GetDataProduct):
            self.report(getResult(self.find_data_product, request.id))
        elif isinstance(request, ChangeConfiguration):
            # changes ServiceApi hostname, port
            request.configuration.apply()

    def _get_resource_registry(self):
        if not self._resource_registry:
            self._resource_registry = ResourceRegistryServiceClient(node=self.agent.container.node)
        return self._resource_registry

    ### perform operations

    def create_instrument(self, instrument):
        """ add all entries into resource registry """
        # TODO: for now use preload to initialize instrument entries in registry

    def list_instruments(self):
        """ perform lookup used by ion-ux to generate list of devices """
        return ServiceApi.find_by_resource_type('InstrumentDevice')

    def find_instrument(self, name):
        """ determine id of device with given name """
        log.debug("searching for instrument with name: %s", name)
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
        try:
            step = "starting agent"
            log.debug('starting agent for device %s', device_id)
            response = ServiceApi.instrument_agent_start(device_id)                                        # launches instrument agent (not yet driver)
            time.sleep(30)
            # if response is success...
            step = "initialize agent (start driver)"
            log.debug('commanding agent: initialize device %s', device_id)
            response = ServiceApi.instrument_execute_agent(device_id, 'RESOURCE_AGENT_EVENT_INITIALIZE')   # cause agent to start driver process
            # if response is success...
            step = "connect agent to device"
            log.debug('commanding agent: go_active device %s', device_id)
            response = ServiceApi.instrument_execute_agent(device_id, 'RESOURCE_AGENT_EVENT_GO_ACTIVE')    # cause driver to connect to device
            # if response is success...
            step = "put device into command mode"
            log.debug('commanding agent: run device %s', device_id)
            response = ServiceApi.instrument_execute_agent(device_id, 'RESOURCE_AGENT_EVENT_RUN')          # put agent/driver into command mode
            # if response is success...
            step = "command device to begin streaming"
            log.debug('commanding agent: go_streaming device %s', device_id)
            response = ServiceApi.instrument_execute_agent(device_id, 'DRIVER_EVENT_START_AUTOSAMPLE')     # put into streaming mode

            self.report(OperationResult(result='device %s started'%device_id))
        except Exception,e:
            log.warn('failed to start device %s: %s',device_id,e, exc_info=True)
            self.report(OperationResult(result='device %s failed step: %s'%(device_id,step), exception=e))

    def find_data_product(self, device_id):
        rr = self._get_resource_registry()
        # device hasDataProducer
        producer_ids,_ = rr.find_objects(subject=device_id, predicate=PRED.hasDataProducer, object_type=RT.DataProducer, id_only=True)
        if len(producer_ids)==0:
            return None
#        if len(producer_ids)>1:
#            raise IonException('found more than one producer for device ' + device_id + ': ' + repr(producer_ids))
        # data product hasDataProducer
        product_ids,_ = rr.find_subjects(object=producer_ids[0], predicate=PRED.hasDataProducer, subject_type=RT.DataProduct, id_only=True)
        if len(product_ids)==0:
            return None
        if len(product_ids)>1:
            raise IonException('found more than one data product for device ' + device_id + ': ' + repr(product_ids))
        return product_ids[0]

    def stop_device(self, instrument):
        """ stop driver/agent processes """
