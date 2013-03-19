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
    def __init__(self, id, timeout=300):
        self.id = id
        self.timeout = timeout
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
            self.start_device(request.id, request.timeout)
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
        out = ServiceApi.find_by_resource_type('InstrumentDevice')
        log.trace('out: %r', out)
        while isinstance(out[0], list):
            log.warn('have list of lists -- should have list of devices!')
            out = out[0]
            log.trace('out: %r', out)
        return out

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

    def start_device(self, device_id, timeout=300):
        """ start necessary drivers and agents for instrument, put into streaming mode """
        start_time = time.time()
        give_up_time = start_time + timeout
        pause_time = 5 # too big = wait longer than needed ; too small = check too frequently
        try:
            log.debug('starting agent for device %s', device_id)
            ServiceApi.instrument_agent_start(device_id)                                        # launches instrument agent (not yet driver)
        except Exception,e:
            log.warn('failed to start device %s: %s',device_id,e, exc_info=True)
            self.report(OperationResult(result='failed to start device '+device_id, exception=e))
            return
        wait_begin = time.time()
        all_times = { 'process': wait_begin-start_time }
        for cmd in [ 'RESOURCE_AGENT_EVENT_INITIALIZE', 'RESOURCE_AGENT_EVENT_GO_ACTIVE', 'RESOURCE_AGENT_EVENT_RUN', 'DRIVER_EVENT_START_AUTOSAMPLE' ]:
            attempt=0
            while True:
                attempt += 1
                log.debug('[%d] sending command to device %s agent: %s', attempt, device_id, cmd)
                try:
                    execution_start = time.time()
                    try:
                        ServiceApi.instrument_execute_agent(device_id, cmd)
                    except ApeException as ae:
                        # if previous command timed out, it could have succeeded even though it returned an error
                        # HACK assume it did, get better info about state later...
                        if 'Command %s not handled in state'%cmd not in str(ae):
                            raise ae #all other exceptions handle below (retry cmd)
                        else:
                            log.warn("got an error executing %s, but assuming the previous state change was successful", cmd)
                            # continue below as if command succeeded
                    execution_end = time.time()
                    all_times[ 'wait_'+cmd ] = execution_start - wait_begin
                    all_times[ cmd ] = execution_end - execution_start
                    wait_begin = execution_end
                    break # go to next cmd
                except Exception,e:
                    log.warn("[%d] command failed: %s", attempt, e)
                    if time.time() > give_up_time:
                        log.error("giving up after repeated failures")
                        self.report(OperationResult(result='device %s failed at cmd: %s'%(device_id,cmd), exception=e))
                        return
                    time.sleep(pause_time)
        self.report(OperationResult(result=all_times))

    def find_data_product(self, device_id):
        rr = self._get_resource_registry()
        # device hasDataProducer
        producer_ids,_ = rr.find_objects(subject=device_id, predicate=PRED.hasDataProducer, object_type=RT.DataProducer, id_only=True)
        if len(producer_ids)==0:
            return None
        # data product hasDataProducer
        product_ids,_ = rr.find_subjects(object=producer_ids[0], predicate=PRED.hasDataProducer, subject_type=RT.DataProduct, id_only=True)
        if len(product_ids)==0:
            return None
        if len(product_ids)>1:
            raise IonException('found more than one data product for device ' + device_id + ': ' + repr(product_ids))
        return product_ids[0]

    def stop_device(self, instrument):
        """ stop driver/agent processes """
