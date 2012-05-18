''' integration test component to inject simulated instrument data into ION '''

# TODO:
# change config to specify a target # msgs
# add operation to report actual # msgs
# adapt sleep to approach target # msgs

from ape.common.types import ApeComponent, ApeException, ApeRequest
from ape.component.instruments import build_instrument
from ape.common.requests import StartRequest, StopRequest, RegisterWithContainer, PerformanceResult
from pyon.public import PRED, RT, log, IonObject, StreamPublisherRegistrar
from interface.services.dm.ipubsub_management_service import PubsubManagementServiceClient
from interface.services.coi.iresource_registry_service import ResourceRegistryServiceClient
from interface.services.sa.iinstrument_management_service import InstrumentManagementServiceClient
from interface.services.sa.idata_acquisition_management_service import DataAcquisitionManagementServiceClient
from interface.services.sa.idata_product_management_service import DataProductManagementServiceClient

from math import sin
from time import time, sleep
from threading import Thread
import traceback

import pickle

class Configuration(object):
    def __init__(self, data_product, interval_seconds, instrument_configuration=None, sleep_even_zero=True,
                 easy_registration=True, persist_product=False,
                 timing_rate=500, log_timing=True, report_timing=True, include_size=False):
        self.data_product = data_product
        self.interval = interval_seconds           # target rate (seconds) to publish a granule
        self.instrument = build_instrument(instrument_configuration)
        self.easy_registration = easy_registration # register as needed, skip if already registered
        self.report_timing = report_timing         # report time in publish, granule size back to manager?
        self.log_timing = log_timing               # log time in publish, granule size to container logfile?
        self.timing_rate = timing_rate             # how often to log/report publish, granule size
        self.include_size = include_size           # include size of granule object in report to manager?
        self.persist_product = persist_product     # use container persistence for data product?
        self.sleep_even_zero = sleep_even_zero     # if sleep time is zero, sleep anyway?

class InstrumentSimulator(ApeComponent):

    def __init__(self, component_id, agent, configuration):
        ApeComponent.__init__(self, component_id, agent, configuration)

    model_id = None
    keep_running = True
    emit_granules = False
    thread = None

    def _start(self):
        # interact with container
        self.resource_registry = ResourceRegistryServiceClient(node=self.agent.container.node)
        self.pubsubclient = PubsubManagementServiceClient(node=self.agent.container.node)
        self.imsclient = InstrumentManagementServiceClient(node=self.agent.container.node)
        self.damsclient = DataAcquisitionManagementServiceClient(node=self.agent.container.node)
        self.data_product_client = DataProductManagementServiceClient(node=self.agent.container.node)
        self.stream_publisher_registrar = StreamPublisherRegistrar(process=self.agent,node=self.agent.container.node)

        # add appropriate entries to the pycc registry
        if self.configuration.easy_registration:
            self.register()

        # begin loop to generate/send data
        self.thread = self._DataEmitter(self)
        self.thread.start()

    def _stop(self):
        log.debug("stopping instrument")
        self.stop_sending()
        self.keep_running = False

    def perform_action(self, request):
        log.debug('instrument simulator performing action ' + str(request))
        if isinstance(request, StartRequest):
            self.start_sending()
        elif isinstance(request, StopRequest):
            self.stop_sending()
        elif isinstance(request, RegisterWithContainer):
            self.register()
        else:
            raise ApeException('instrument simulator does not know how to: ' + str(request))
        
    def register(self):
        ''' create entries in resource registry for this instrument '''
        # TODO: handle more than one ID returned from registry
        # TODO: fail if request register but already in registry (and not easy_registration)
        # TODO: should register device agent
        product_ids,_ = self.resource_registry.find_resources(RT.DataProduct, None, self.configuration.data_product, id_only=True)
        if len(product_ids) > 0:
            if self.configuration.easy_registration:
                self.data_product_id = product_ids[0]
            else:
                raise ApeException('should not find data product in registry until i add it: ' + self.configuration.data_product)
        else:
            log.debug('adding data product to the registry')
            # Create InstrumentDevice
            device = IonObject(RT.InstrumentDevice, name=self.configuration.data_product, description='instrument simulator', serial_number=self.configuration.data_product )
            device_id = self.imsclient.create_instrument_device(instrument_device=device)
            self.imsclient.assign_instrument_model_to_instrument_device(instrument_model_id=self._get_model_id(), instrument_device_id=device_id)
            # create a stream definition
            data_product = IonObject(RT.DataProduct,name=self.configuration.data_product,description='ape producer')
            self.data_product_id = self.data_product_client.create_data_product(data_product=data_product, stream_definition_id=self._get_streamdef_id())
            self.damsclient.assign_data_product(input_resource_id=device_id, data_product_id=self.data_product_id)
            if self.configuration.persist_product:
                self.data_product_client.activate_data_product_persistence(data_product_id=self.data_product_id, persist_data=True, persist_metadata=True)

        # get/create producer id
#        producer_ids, _ = self.clients.resource_registry.find_objects(self.data_product_id, PRED.hasDataProducer, RT.DataProducer, id_only=True)
#        if len(producer_ids)>0:
#            log.debug('data producer already in the registry')
#            self.data_producer_id = producer_ids[0]
#        else:
        self.data_producer_id = 'UNUSED'

        self._create_publisher()

    def _get_model_id(self):
        if self.model_id is None:
            try:
                self.model_id = self._read_model_id()
                self.model_id = self._read_model_id()
            except:
                model = IonObject(RT.InstrumentModel, name=self.configuration.instrument.model_name) #, description=self.configuration.model_name, model_label=self.data_source_name)
                self.model_id = self.imsclient.create_instrument_model(model)
        return self.model_id

    def _read_model_id(self):
        # debug reading instrument model
        try_this = self.resource_registry.find_resources(restype=RT.InstrumentModel, id_only=True)
        model_ids = self.resource_registry.find_resources(restype=RT.InstrumentModel, id_only=True, name=self.configuration.instrument.model_name)
        return model_ids[0][0]

    def _get_streamdef_id(self):
        #TODO: figure out how to read existing RAW definition instead of just creating
        #try:
            #stream_type = self.pubsubclient.read_stream_definition()
        stream_def_id = self.pubsubclient.create_stream_definition(container=self.configuration.instrument.stream_definition, name='RAW stream')
        return stream_def_id

    def _create_publisher(self):
        stream_ids, _ = self.resource_registry.find_objects(self.data_product_id, PRED.hasStream, None, True)
        self.publisher = self.stream_publisher_registrar.create_publisher(stream_ids[0])

    class _DataEmitter(Thread):
        ''' do not make outer class a Thread b/c start() is already meaningful to a pyon process '''
        def __init__(self, instrument):
            Thread.__init__(self)
            self.instrument = instrument
        def run(self):
            self.instrument.run()

    def start_sending(self):
        self.emit_granules = True
    def stop_sending(self):
        self.emit_granules = False

    def run(self):
        ''' main loop: essentially create granule, publish granule, then pause to remain at target rate.
            three lines of the useful code marked with ###, everything else is timing/reporting.
        '''
        target_iteration_time = sleep_time = self.configuration.interval
        first_batch = True
        granule_count = iteration_count = granule_sum_size = 0
        granule_elapsed_seconds = publish_elapsed_seconds = sleep_elapsed_seconds = iteration_elapsed_seconds = 0.
        do_timing = self.configuration.report_timing or self.configuration.log_timing

        while self.keep_running:
            if self.emit_granules:
                adjust_timing = True
                iteration_start = granule_start = time()
                if do_timing:
                    granule_count+=1

                ### step 1: create granule
                granule = self.configuration.instrument.get_granule(time=time())

                if do_timing:
                    granule_end = publish_start = time()

                try:
                    ### step 2: publish granule
                    log.debug(self.component_id + ' publishing granule')
                    self.publisher.publish(granule)
                except Exception as e:
                    if self.keep_running:
                        raise e
                    else:
                        # while blocking on publish(), async call may have closed connection
                        # so eat exception and return cleanly
                        return

                if do_timing:
                    publish_end = time()
                    granule_elapsed_seconds += (granule_end - granule_start)
                    publish_elapsed_seconds += (publish_end - publish_start)
                    pickled_granule = pickle.dumps(granule)
                    granule_size = len(pickled_granule)
                    granule_sum_size += granule_size
                    sleep_start = time()

                ### step 3: sleep to maintain configured rate
                if sleep_time>0 or self.configuration.sleep_even_zero:
                    sleep(sleep_time)

                if do_timing:
                    sleep_end = time()
                    sleep_elapsed_seconds += (sleep_end-sleep_start)

                    if granule_count%self.configuration.timing_rate==0:
                        # skip initial batch of timing -- can be skewed b/c one instrument start before the other,
                        # so first instrument works against a more idle system
                        if first_batch:
                            granule_count = granule_elapsed_seconds = publish_elapsed_seconds = sleep_elapsed_seconds = 0.
                            first_batch = False
                            run_start_time = time()
                        else:
                            adjust_timing = False
                            if self.configuration.log_timing:
                                log.info('%s: granule: %f, publish: %f, sleep: %f, size %f' %
                                          (self.configuration.data_product, granule_elapsed_seconds/granule_count,
                                           publish_elapsed_seconds/granule_count, sleep_elapsed_seconds/granule_count,
                                           granule_sum_size/granule_count))
                            if self.configuration.report_timing:
                                report = { 'count': granule_count,
                                           'time': time() - run_start_time,
                                           'publish':publish_elapsed_seconds/granule_count,
                                           'granule':granule_elapsed_seconds/granule_count,
                                           'sleep': sleep_elapsed_seconds/granule_count,
                                           'iteration': iteration_elapsed_seconds/iteration_count }
                                if self.configuration.include_size:
                                    report['size'] = granule_sum_size
                                message = PerformanceResult(report)
                                self.report(message)

                if adjust_timing:
                    iteration_count+=1
                    iteration_end = time()
                    actual_iteration_time = iteration_end - iteration_start
                    iteration_elapsed_seconds += actual_iteration_time
                    adjustment = target_iteration_time - actual_iteration_time
                    sleep_time = max(sleep_time + adjustment, 0)

            else:
                # if not emitting granules, don't do timing either
                sleep(self.configuration.interval)
