''' simple data product consumer that receives data from an endpoint and throws it away. '''


from uuid import uuid4 as unique
from ion.services.dm.utility.granule import RecordDictionaryTool
#from pyon.ion.transform import TransformDataProcess
import logging as log

from ape.common.types import ApeComponent, ApeException
from ape.common.requests import StartRequest, StopRequest, RegisterWithContainer
from pyon.public import PRED, RT, log, IonObject
from interface.services.dm.ipubsub_management_service import PubsubManagementServiceClient
from interface.services.coi.iresource_registry_service import ResourceRegistryServiceClient
from interface.services.dm.itransform_management_service import TransformManagementServiceClient

class Configuration(object):
    def __init__(self, data_product, log_value=False):
        self.data_product = data_product
        self.log_value = log_value

class DataProductConsumer(ApeComponent):
    def __init__(self, name, agent, configuration):
        unique_string = name + "_" + str(unique())
        self.process_name = 'ape_consumer_' + unique_string
        self.easy_registration = True
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
        pubsub_management = PubsubManagementServiceClient(node=self.agent.container.node)
        self.resource_registry = ResourceRegistryServiceClient(node=self.agent.container.node)
        self.transform_management = TransformManagementServiceClient(node=self.agent.container.node)
        data_product_objs,_ = self.resource_registry.find_resources(restype=RT.DataProduct, name=self.configuration.data_product)
        if not len(data_product_objs):
            raise ApeException('did not find data product for name: ' + self.configuration.data_product)
        stream_ids,_ = self.resource_registry.find_resources(RT.Stream, name=self.configuration.data_product)
        subscription_id = pubsub_management.create_subscription(name=self.process_name + '_exchange', stream_ids=stream_ids)
        self.transform = self.transform_management.create_transform(name=self.process_name + '_transform', in_subscription_id=subscription_id,process_definition_id=self._get_process_definition_id())

    def register_process_definition(self):
        # Create process definitions which will used to spawn off the transform processes
        process_definition = IonObject(RT.ProcessDefinition, name='ape_consumer_process')
        if self.configuration.log_value:
            process_definition.executable = { 'module': 'ape.component.consumer', 'class':'_LogValueTransform' }
        else:
            process_definition.executable = { 'module': 'ape.component.consumer', 'class':'_NoOpTransform' }
#        process_definition.executable = { 'module': 'ape.component.consumer', 'class':'_NoOpTransform' }
        process_definition_id, _ = self.resource_registry.create(process_definition)
        return process_definition_id

    def enable_transform(self):
        self.transform_management.activate_transform(self.transform)

    def disable_transform(self):
        self.transform_management.deactivate_transform(self.transform)

    def _stop(self):
        self.transform_management.delete_transform(self.transform)

    def perform_action(self, request):
        if isinstance(request, StartRequest):
            self.enable_transform()
        elif isinstance(request, StopRequest):
            self.disable_transform()
        elif isinstance(request, RegisterWithContainer):
            self.register_process_definition()


#class _NoOpTransform(TransformDataProcess):
#    def on_start(self):
#        log.debug('starting transform')
#    def process(self, granule):
#        pass
#        log.debug('ignoring message: ' + repr(granule))
#        try:
#            log.debug('granule dictionary: ' + repr(granule.__dict__))
#            log.debug('granule records: ' + repr(granule.record_dictionary))
#            pass
##            value = granule.record_dictionary['value']
##            log.info('received value from data product: ' + value)
#        except:
#            log.info('exception unpacking granule: ' + granule)
#        pass

#class _LogValueTransform(TransformDataProcess):
#    def on_start(self):
#        super(TransformDataProcess,self).on_start()
#        log.debug('starting transform')
#    def process(self, granule):
#        tool = RecordDictionaryTool.load_from_granule(granule)
#        msg = ''
#        for (k,v) in tool.iteritems():
#            msg += '\n\t' + repr(k) + " => " + repr(v)
#        if msg:
#            log.debug('have granule with payload:' + msg)
#        else:
#            log.info('have empty granule')
