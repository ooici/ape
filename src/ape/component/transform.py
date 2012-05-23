''' simple data product consumer that receives data from an endpoint and throws it away. '''


from uuid import uuid4 as unique
from interface.services.sa.idata_product_management_service import DataProductManagementServiceClient
from prototype.sci_data.constructor_apis import StreamDefinitionConstructor
from pyon.ion.granule.record_dictionary import RecordDictionaryTool
from pyon.ion.granule.taxonomy import TaxyTool
from pyon.ion.transform import TransformDataProcess
import logging as log

from ape.common.types import ApeComponent, ApeException
from ape.common.requests import StartRequest, StopRequest, RegisterWithContainer
from pyon.public import PRED, RT, log, IonObject, StreamPublisherRegistrar
from interface.services.dm.ipubsub_management_service import PubsubManagementServiceClient
from interface.services.coi.iresource_registry_service import ResourceRegistryServiceClient
from interface.services.dm.itransform_management_service import TransformManagementServiceClient
from interface.objects import StreamQuery
from pyon.ion.granule.granule import build_granule
import pickle
from numpy import array, ndarray

def identity(input_record_dictionary):
    out = { }
    for (k,v) in input_record_dictionary.iteritems():
        out[k] = v
    return out

class Configuration(object):
    def __init__(self, persist_product=False, transform_function=identity):
        self.input_data_products = []
        self.output_data_products = []
        self.persist_product = persist_product
        self.field_names = []
        self.tax = None
        self.transform_function = transform_function
    def add_input(self, data_product):
        self.input_data_products.append(data_product)
    def add_output(self, data_product):
        self.output_data_products.append(data_product)
    def add_output_field(self, field):
        self.field_names.append(field)
    def get_taxonomy(self):
        if not self.tax:
            self.tax = TaxyTool()
            for field in self.field_names:
                self.tax.add_taxonomy_set(field)
        return self.tax
    def get_transform_config(self):
        return { 'function': pickle.dumps(self.transform_function), 'fields': self.field_names }

class TransformComponent(ApeComponent):
    def __init__(self, name, agent, configuration):
        unique_string = name + "_" + str(unique())
        self.process_name = 'ape_transform_' + unique_string
        self.easy_registration = True
        super(TransformComponent,self).__init__(name, agent, configuration)

    def _start(self):
        log.debug('transform starting')

        # access container resources
        self.pubsub_management = PubsubManagementServiceClient(node=self.agent.container.node)
        self.resource_registry = ResourceRegistryServiceClient(node=self.agent.container.node)
        self.transform_management = TransformManagementServiceClient(node=self.agent.container.node)
        self.data_product_client = DataProductManagementServiceClient(node=self.agent.container.node)

        # subscribe to input streams
        all_stream_ids = []
        for data_product in self.configuration.input_data_products:
            data_product_objs,_ = self.resource_registry.find_resources(restype=RT.DataProduct, name=data_product)
            if not len(data_product_objs):
                raise ApeException('did not find data product for name: ' + data_product)
            #        stream_ids,_ = self.resource_registry.find_objects(self.configuration.data_product, PRED.hasStream, None, True)
            stream_ids,_ = self.resource_registry.find_resources(RT.Stream, name=data_product)
            stream_id = stream_ids[0]
            #        stream_id = data_product_objs[0].stream_definition_id
            stream_definition_id = self.pubsub_management.find_stream_definition(stream_id=stream_id, id_only=True)
            all_stream_ids.append(stream_id)
        query = StreamQuery(all_stream_ids)
        subscription_id = self.pubsub_management.create_subscription(query=query, exchange_name=self.process_name + '_exchange')

        output_dictionary = self._register_output_products()
        self.transform = self.transform_management.create_transform(name=self.process_name + '_transform',
                                                in_subscription_id=subscription_id, out_streams=output_dictionary,
                                                process_definition_id=self._get_process_definition_id(), configuration=self.configuration.get_transform_config())

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

    def register_process_definition(self):
        # Create process definitions which will used to spawn off the transform processes
        process_definition = IonObject(RT.ProcessDefinition, name='ape_consumer_process')
        process_definition.executable = { 'module': 'ape.component.transform', 'class':'_Transform' }
        process_definition_id, _ = self.resource_registry.create(process_definition)
        return process_definition_id


    # TODO: this should be delegated to transform configuration
    def _get_streamdef_id(self):
        sdc = StreamDefinitionConstructor(description='Parsed conductivity temperature and pressure observations from a Seabird 37 CTD', nil_value=-999.99, encoding='hdf5')
        sdc.define_temporal_coordinates(reference_frame='http://www.opengis.net/def/trs/OGC/0/GPS', definition='http://www.opengis.net/def/property/OGC/0/SamplingTime',
            reference_time='1970-01-01T00:00:00Z', unit_code='s' )
        sdc.define_geospatial_coordinates(definition="http://www.opengis.net/def/property/OGC/0/PlatformLocation",reference_frame='urn:ogc:def:crs:EPSG::4979')

        # TODO: remove unit, range, definition
        # used only in old-style granule
        sdc.define_coverage(field_name='value',
            field_definition="urn:x-ogc:def:phenomenon:OGC:temperature",
            field_units_code='Cel',
            field_range=[-99999.0, 99999.0])
        stream_definition = sdc.close_structure()
        stream_def_id = self.pubsub_management.create_stream_definition(container=stream_definition, name='RAW stream')
        return stream_def_id

    def _register_output_products(self):
        out = {} # data_product_name --> stream_id
        for data_product_name in self.configuration.output_data_products:
            product_ids,_ = self.resource_registry.find_resources(RT.DataProduct, None, name=data_product_name, id_only=True)
            if len(product_ids):
                log.debug('data product was already in the registry')
                self.data_product_id = product_ids[0]
            else:
                data_product = IonObject(RT.DataProduct, name=data_product_name, description='ape transform')
                self.data_product_id = self.data_product_client.create_data_product(data_product=data_product, stream_definition_id=self._get_streamdef_id())
            #                self.damsclient.assign_data_product(input_resource_id=device_id, data_product_id=self.data_product_id)
            if self.configuration.persist_product:
                self.data_product_client.activate_data_product_persistence(data_product_id=self.data_product_id, persist_data=True, persist_metadata=True)
            stream_ids,_ = self.resource_registry.find_resources(RT.Stream, name=data_product_name, id_only=True)
            if len(stream_ids):
                out[data_product_name] = stream_ids[0]
            else:
                raise ApeException('could not find stream ID after registered output: ' + data_product_name)
        return out

    def _stop(self):
        self.transform_management.delete_transform(self.transform)

    def perform_action(self, request):
        if isinstance(request, StartRequest):
            self.enable_transform()
        elif isinstance(request, StopRequest):
            self.disable_transform()
        elif isinstance(request, RegisterWithContainer):
            self.register_process_definition()

    def enable_transform(self):
        self.transform_management.activate_transform(self.transform)

    def disable_transform(self):
        self.transform_management.deactivate_transform(self.transform)

class _Transform(TransformDataProcess):
    tax = None
    def get_taxonomy(self):
        if not self.tax:
            self.tax = TaxyTool()
            for field in self.field_names:
                self.tax.add_taxonomy_set(field)
        return self.tax
    def on_start(self):
        super(TransformDataProcess,self).on_start()
        configuration = self.CFG #['ape-transform-configuration']
        self.transform_code = pickle.loads(configuration['function'])
        self.field_names = configuration['fields']

    def process(self, granule_in):
        log.debug('staring process')
        try:
            input = RecordDictionaryTool.load_from_granule(granule_in)
            output = {}
#            log.debug('have granule: ' + repr(input))
            ## WARNING! WARNING! this works for internal ape testing,
            ## but is not appropriate for use in project code
            exec self.transform_code

            if output:
                payload = self.convert_values(output)
                granule_out = build_granule(data_producer_id='UNUSED', taxonomy=self.get_taxonomy(), record_dictionary=payload)
                self.publish(granule_out)
        except Exception as ex:
            ## UGLY! i shouldn't have to do this, but otherwise the container silently drops the exception...
            log.debug('exception in transform process', exc_info=True)
            raise ex

    def convert_values(self, dictionary):
        payload = RecordDictionaryTool(self.get_taxonomy())
        for (k,v) in dictionary.iteritems():
            if isinstance(v, tuple) or isinstance(v, list):
                payload[k] = array(v)
            elif isinstance(v, ndarray):
                payload[k] = v
            elif isinstance(v, dict):
                raise ApeException('not yet able to put dictionary inside another')
            else:
                payload[k] = array((v,))
        return payload

