''' simple data product consumer that receives data from an endpoint and throws it away. '''


from uuid import uuid4 as unique
from ion.services.dm.utility.granule import RecordDictionaryTool
#from pyon.ion.transform import TransformDataProcess
from ion.core.process.transform import TransformStreamListener
import logging as log

from ape.common.types import ApeComponent, ApeException
from ape.common.requests import StartRequest, StopRequest, RegisterWithContainer
from pyon.public import PRED, RT, log, IonObject
from interface.services.dm.ipubsub_management_service import PubsubManagementServiceClient
from interface.services.coi.iresource_registry_service import ResourceRegistryServiceClient
from interface.services.dm.itransform_management_service import TransformManagementServiceClient
from pyon.container.procs import IMMEDIATE_PROCESS_TYPE, STREAM_PROCESS_TYPE

class Configuration(object):
    def __init__(self, data_product, log_value=False):
        self.data_product = data_product
        self.log_value = log_value

class DataProductConsumer(ApeComponent):
    def __init__(self, name, agent, configuration):
        unique_string = name + "_" + str(unique())
        self.process_name = 'ape_consumer_' + unique_string
        self.easy_registration = True
        self._transform_pid = None
        super(DataProductConsumer,self).__init__(name, agent, configuration)

    def _get_process_definition_id(self):
        if self.easy_registration:
            try:
                return self._read_process_definition_id()
            except:
                return self.register_process_definition()
        else:
            return self._read_process_definition_id()


    def _read_process_definition_id(self):
        process_ids,_ = self.resource_registry.find_resources(restype=RT.ProcessDefinition, lcstate=None, name=self.process_name, id_only=True)
        return process_ids[0]

    def _start(self):
        log.debug('consumer starting')
        self.resource_registry = ResourceRegistryServiceClient(node=self.agent.container.node)

    def enable_transform(self):
        product_ids,_ = self.resource_registry.find_resources(RT.DataProduct, None, self.configuration.data_product, id_only=True)
        if len(product_ids)>0:
            log.info('have registry entry, using id: %s', product_ids[0])
            dp = product_ids[0]
        else:
            # config = {'process':{'type':IMMEDIATE_PROCESS_TYPE, 'procinner': 'level2'}, 'base': 'level1'}
            dp = self.configuration.data_product
        process_config = {'process':{'type':STREAM_PROCESS_TYPE, 'queue_name': dp }}
        log.info('starting consumer on exchange: ' + dp)
        self._transform_pid = self.agent.container.proc_manager.spawn_process('ape_consumer_'+dp, 'ape.component.consumer', '_NoOpTransform', process_config)

    def disable_transform(self):
        pass

    def _stop(self):
        pass

    def perform_action(self, request):
        if isinstance(request, StartRequest):
            self.enable_transform()
        elif isinstance(request, StopRequest):
            self.disable_transform()
        #elif isinstance(request, RegisterWithContainer):
            # self.register_process_definition()

### simple TEST transforms to demonstrate component

class _NoOpTransform(TransformStreamListener):

   def on_start(self):
       log.debug('starting transform')
       super(_NoOpTransform,self).on_start()
       log.info('process config: %r', self.CFG)

   def process(self, granule):
       log.debug('ignoring message: ' + repr(granule))
       try:
           log.debug('granule dictionary: ' + repr(granule.__dict__))
           log.debug('granule records: ' + repr(granule.record_dictionary))
           #value = granule.record_dictionary['value']
           #log.info('received value from data product: ' + value)
           pass
       except:
           log.info('exception unpacking granule: ' + granule)
   def call_process(self, message, stream_route, stream_id):
       #*a, **b):
       #log.info('call_process args:\n*a = %r\n**b = %r', a, b)
       pass

class _LogValueTransform(TransformStreamListener):

   def on_start(self):
       super(_LogValueTransform,self).on_start()
       log.debug('starting transform')

   def recv_packet(self, granule, stream_route, stream_id):
       tool = RecordDictionaryTool.load_from_granule(granule)
       msg = ''
       for (k,v) in tool.iteritems():
           msg += '\n\t' + repr(k) + " => " + repr(v)
       if msg:
           log.debug('have granule with payload:' + msg)
       else:
           log.info('have empty granule')
