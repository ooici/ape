''' simple data product consumer that receives data from an endpoint and throws it away. '''
from threading import Thread, Lock
from time import sleep

from uuid import uuid4 as unique
from interface.services.sa.idata_product_management_service import DataProductManagementServiceClient
from prototype.sci_data.constructor_apis import StreamDefinitionConstructor
from pyon.ion.granule.record_dictionary import RecordDictionaryTool
from pyon.ion.granule.taxonomy import TaxyTool
from pyon.ion.transform import TransformDataProcess
#import logging as log
import time

from ape.common.types import ApeComponent, ApeException
from ape.common.requests import StartRequest, StopRequest, RegisterWithContainer, PerformanceResult
from pyon.public import PRED, RT, log, IonObject, StreamPublisherRegistrar, StreamSubscriberRegistrar
from interface.services.dm.ipubsub_management_service import PubsubManagementServiceClient
from interface.services.coi.iresource_registry_service import ResourceRegistryServiceClient
from interface.services.dm.itransform_management_service import TransformManagementServiceClient
from interface.objects import StreamQuery
from pyon.ion.granule.granule import build_granule
import pickle
from numpy import array, ndarray
from ion.services.dm.utility.granule_utils import CoverageCraft

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
        self.log_stats = True
        self.report_stats = False
        self.stats_interval = 60
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
        return { 'function': pickle.dumps(self.transform_function),
                 'fields': self.field_names,
                 'stats_interval': self.stats_interval,
                 'log_stats': self.log_stats,
                 'report_stats': self.report_stats }

class TransformComponent(ApeComponent):
    def __init__(self, name, agent, configuration):
        super(TransformComponent,self).__init__(name, agent, configuration)
        unique_string = name + "_" + str(unique())
        self.process_name = 'ape_transform_' + unique_string
        self.stats_stream_name = self.process_name + '_stats'
        self.easy_registration = True

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
        if self.configuration.stats_interval>0:
            stream_id = output_dictionary['stats_stream']
            self._enable_stats_callback(stream_id)
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
            out[data_product_name] = self._get_stream_id(data_product_name)
        if self.configuration.stats_interval>0:
            self.stats_stream_id = self._get_stream_id(self.stats_stream_name)
            out['stats_stream'] = self.stats_stream_id
        return out

    def _get_stream_id(self, data_product_name):
        product_ids,_ = self.resource_registry.find_resources(RT.DataProduct, None, name=data_product_name, id_only=True)
        if len(product_ids):
            log.debug('data product was already in the registry')
            self.data_product_id = product_ids[0]
        else:
            craft = CoverageCraft
            sdom, tdom = craft.create_domains()
            sdom = sdom.dump()
            tdom = tdom.dump()
            parameter_dictionary = craft.create_parameters()
            parameter_dictionary = parameter_dictionary.dump()

            data_product = IonObject(RT.DataProduct, name=data_product_name, description='ape transform', spatial_domain=sdom, temporal_domain=tdom)
            self.data_product_id = self.data_product_client.create_data_product(data_product=data_product,
                stream_definition_id=self._get_streamdef_id(), parameter_dictionary=parameter_dictionary)
            #                self.damsclient.assign_data_product(input_resource_id=device_id, data_product_id=self.data_product_id)
        if self.configuration.persist_product:
            self.data_product_client.activate_data_product_persistence(data_product_id=self.data_product_id, persist_data=True, persist_metadata=True)
        stream_ids,_ = self.resource_registry.find_resources(RT.Stream, name=data_product_name, id_only=True)
        if len(stream_ids):
            return stream_ids[0]
        else:
            raise ApeException('could not find stream ID after registered output: ' + data_product_name)

    def _enable_stats_callback(self, stream_id):
        log.debug('registering stats callback')
        exchange = self.process_name+'_stats'
        query = StreamQuery([stream_id])
        subscription_id = self.pubsub_management.create_subscription(query=query, exchange_name=exchange)
        subscription = self.pubsub_management.read_subscription(subscription_id)
        subscriber_registrar = StreamSubscriberRegistrar(process=self.agent, container=self.agent.container)
        subscriber = subscriber_registrar.create_subscriber(exchange_name=exchange, callback=self._on_stats_message)
        subscriber.start()
        self.pubsub_management.activate_subscription(subscription_id=subscription_id)

    def _on_stats_message(self, stats_granule, headers):
        log.debug('relaying stats message')
        stats = RecordDictionaryTool.load_from_granule(stats_granule)
        message = PerformanceResult(stats)
        self.report(message)

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
    lock = Lock()
    start_time = None
    count=0
    def on_start(self):
        super(_Transform,self).on_start()
        self.tax = TaxyTool()
        for field in self.CFG['fields']:
            self.tax.add_taxonomy_set(field)
        self.transform_code = pickle.loads(self.CFG['function'])
        interval = int(self.CFG['stats_interval'])
        log_stats = self.CFG['log_stats']
        report_stats = self.CFG['report_stats']
        if interval>0 and (log_stats or report_stats):
            self.stats_tax = TaxyTool()
            for field in 'count','elapsed':
                self.stats_tax.add_taxonomy_set(field)
            pub = getattr(self, 'stats_stream') if report_stats else None
            log.error('stats stream is %r', pub)
            log_name = getattr(self, 'name') if log_stats else None
            self.reporter = _ReportingThread(self, pub, log_name, interval)
            self.reporter.start()

    def on_stop(self):
        self.reporter.keep_running = False
        self.reporter = None
        super(_Transform,self).on_stop()
    def process(self, granule_in):
        log.debug('received granule')
        self.update_stats()
        try:
            input = RecordDictionaryTool.load_from_granule(granule_in)
            output = {}
#            log.debug('have granule: ' + repr(input))

            ## WARNING! WARNING! this works for internal ape testing,
            ## but is not appropriate for use in project code
            if self.transform_code:
                exec self.transform_code

            if output:
                payload = self.convert_values(output, self.tax)
                granule_out = build_granule(data_producer_id='UNUSED', taxonomy=self.tax, record_dictionary=payload)
                self.publish_output(granule_out)
        except Exception as ex:
            ## UGLY! i shouldn't have to do this, but otherwise the container silently drops the exception...
#            log.debug('exception in transform process', exc_info=True)
            ## EVEN UGLIER! Logging system fails to print stack
            import traceback
            log.error('exception in transform process %s\n%s', ex, traceback.format_exc())
            raise ex

    def publish_output(self,msg):
        """ override TransformDataProcess._publish_all: just send to output streams """
        if not self._pub_init:
            self._pub_init = True
            self.publishers = []
            for name,stream in self.streams.iteritems():
                if name!='stats_stream':
                    self.publishers.append(getattr(self,name))
        for publisher in self.publishers:
            publisher.publish(msg)

    def convert_values(self, dictionary, taxonomy):
        payload = RecordDictionaryTool(taxonomy)
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

    def update_stats(self):
        with self.lock:
            self.count+=1
            if not self.start_time:
                self.start_time = time.time()
    def get_stats(self):
        with self.lock:
            if self.start_time:
                return {'count':self.count,
                        'elapsed':time.time()-self.start_time}
            else:
                return {'count':0, 'elapsed':0}

class _ReportingThread(Thread):
    """ thread started by transform to report stats periodically """
    def __init__(self, target, publisher, log_name, interval):
        super(_ReportingThread,self).__init__()
        self.target = target
        self.publisher = publisher
        self.keep_running = True
        self.interval = interval
        self.log_name = log_name
    def run(self):
        log.debug('reporting stats every %f sec', self.interval)
        while self.keep_running:
            stats = self.target.get_stats()
            if self.log_name:
                log.info(self.log_name + ' stats: ' + str(stats))
            if self.publisher:
                stats_rd = self.target.convert_values(stats,self.target.stats_tax)
                stats_granule = build_granule(data_producer_id='UNUSED', taxonomy=self.target.stats_tax, record_dictionary=stats_rd)
                self.publisher.publish(stats_granule)
            sleep(self.interval)
