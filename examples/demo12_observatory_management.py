"""
ape sample: observatory management

test components that connect to service gateway and control device agents
"""

import gevent.monkey
from threading import Lock
import time
from ape.component.sandbag import ResourceWaster
from ape.component.transform import TransformComponent
from ape.component.transform import Configuration as TransformConfiguration

gevent.monkey.patch_all(aggressive=False)

from ape.common.types import ApeException
from ape.common.requests import OperationResult
from ape.manager.simple_manager import SimpleManager, InventoryListener, Listener
from ape.common.requests import PingRequest, AddComponent, StartRequest, InventoryRequest, StopRequest, PerformanceResult, ChangeConfiguration
from ape.component.instrument_controller import *
from ape.component.consumer import DataProductConsumer
from ape.component.consumer import Configuration as ConsumerConfiguration
from ape.common.messages import  component_id, agent_id, component_type
from time import sleep
import math
from gevent.event import AsyncResult
from ape.component.sandbag import Configuration as SandbagConfiguration

def wait(a):
    raw_input('--- press enter to continue ---')
#    sleep(a)


class PerformanceListener(Listener):
    def __init__(self):
        self.latest_data = None
        self.lock = Lock()
        self.prior_count=0
    def on_message(self, message):
        if isinstance(message.result, PerformanceResult):
            try:
                self.lock.acquire()
                if self.latest_data:
                    self.prior_count = self.latest_data.data['count']
                self.latest_data = message.result
            finally:
                self.lock.release()
    def get_rate(self):
        data = self.latest_data.data if self.latest_data else None
        if data and data['elapsed']>0:
            return data['count']/data['elapsed'], data['count']-self.prior_count
        else:
            return 0,0

class AnswerListener(Listener):
    next_result = None
    def on_message(self, message):
        if isinstance(message.result, OperationResult):
            self.handle_message(message.result)
    def expect_message(self):
        if self.next_result:
            raise ApeException('already waiting for a result!')
        self.next_result = AsyncResult()
        return self.next_result
    def handle_message(self, result):
        if self.next_result:
            self.next_result.set(result)
            self.next_result = None

DEVICE_INFO = (
    ['Gummi Flavor, Color, Softness sensor','Gummi FCS Stream parsed 1','Gummi Raw Stream 1'],
    ['Gummi FCS sensor 2','Gummi FCS Stream parsed 2','Gummi Raw Stream 2'],
    ['Gummi FCS sensor 3','Gummi FCS Stream parsed 3','Gummi Raw Stream 3'],
    ['Gummi FCS sensor 4','Gummi FCS Stream parsed 4','Gummi Raw Stream 4'],
    ['Gummi FCS sensor 5','Gummi FCS Stream parsed 5','Gummi Raw Stream 5'],
    ['Gummi FCS sensor 6','Gummi FCS Stream parsed 6','Gummi Raw Stream 6'],
    ['Gummi FCS sensor 7','Gummi FCS Stream parsed 7','Gummi Raw Stream 7'],
    ['Gummi FCS sensor 8','Gummi FCS Stream parsed 8','Gummi Raw Stream 8'],
    ['Gummi FCS sensor 9','Gummi FCS Stream parsed 9','Gummi Raw Stream 9'],
    ['Gummi FCS sensor 10','Gummi FCS Stream parsed 10','Gummi Raw Stream 10'],
    ['Gummi FCS sensor 11','Gummi FCS Stream parsed 11','Gummi Raw Stream 11'],
    ['Gummi FCS sensor 12','Gummi FCS Stream parsed 12','Gummi Raw Stream 12'],
    ['Gummi FCS sensor 13','Gummi FCS Stream parsed 13','Gummi Raw Stream 13'],
    ['Gummi FCS sensor 14','Gummi FCS Stream parsed 14','Gummi Raw Stream 14'],
    ['Gummi FCS sensor 15','Gummi FCS Stream parsed 15','Gummi Raw Stream 15'],
    ['Gummi FCS sensor 16','Gummi FCS Stream parsed 16','Gummi Raw Stream 16'],
    ['Gummi FCS sensor 17','Gummi FCS Stream parsed 17','Gummi Raw Stream 17'],
    ['Gummi FCS sensor 18','Gummi FCS Stream parsed 18','Gummi Raw Stream 18'],
    ['Gummi FCS sensor 19','Gummi FCS Stream parsed 19','Gummi Raw Stream 19'],
    ['Gummi FCS sensor 20','Gummi FCS Stream parsed 20','Gummi Raw Stream 20'],
#
#    ['Gummi FCS sensor 21','Gummi FCS Stream parsed 21','Gummi Raw Stream 21'],
#    ['Gummi FCS sensor 22','Gummi FCS Stream parsed 22','Gummi Raw Stream 22'],
#    ['Gummi FCS sensor 23','Gummi FCS Stream parsed 23','Gummi Raw Stream 23'],
#    ['Gummi FCS sensor 24','Gummi FCS Stream parsed 24','Gummi Raw Stream 24'],
#    ['Gummi FCS sensor 25','Gummi FCS Stream parsed 25','Gummi Raw Stream 25'],
#    ['Gummi FCS sensor 26','Gummi FCS Stream parsed 26','Gummi Raw Stream 26'],
#    ['Gummi FCS sensor 27','Gummi FCS Stream parsed 27','Gummi Raw Stream 27'],
#    ['Gummi FCS sensor 28','Gummi FCS Stream parsed 28','Gummi Raw Stream 28'],
#    ['Gummi FCS sensor 29','Gummi FCS Stream parsed 29','Gummi Raw Stream 29'],
#    ['Gummi FCS sensor 30','Gummi FCS Stream parsed 30','Gummi Raw Stream 30'],
#    ['Gummi FCS sensor 31','Gummi FCS Stream parsed 31','Gummi Raw Stream 31'],
#    ['Gummi FCS sensor 32','Gummi FCS Stream parsed 32','Gummi Raw Stream 32'],
#    ['Gummi FCS sensor 33','Gummi FCS Stream parsed 33','Gummi Raw Stream 33'],
#    ['Gummi FCS sensor 34','Gummi FCS Stream parsed 34','Gummi Raw Stream 34'],
#    ['Gummi FCS sensor 35','Gummi FCS Stream parsed 35','Gummi Raw Stream 35'],
#    ['Gummi FCS sensor 36','Gummi FCS Stream parsed 36','Gummi Raw Stream 36'],
#    ['Gummi FCS sensor 37','Gummi FCS Stream parsed 37','Gummi Raw Stream 37'],
#    ['Gummi FCS sensor 38','Gummi FCS Stream parsed 38','Gummi Raw Stream 38'],
#    ['Gummi FCS sensor 39','Gummi FCS Stream parsed 39','Gummi Raw Stream 39'],
#    ['Gummi FCS sensor 40','Gummi FCS Stream parsed 40','Gummi Raw Stream 40'],
    )

def main():
    WASTE_RAM_PERCENT=.00001
    WASTE_CPU_PERCENT=.00001
    QUICK_LOAD_DEVICES=12

    ans = AnswerListener()
    perf = PerformanceListener()
#    m = SimpleManager()
    m = SimpleManager(broker_hostname='gum')
    m.add_listener(ans)
    m.add_listener(perf)

#    waste_ram_bytes=int(512*1024*1024*WASTE_RAM_PERCENT/100) # gumstix with 512mb
#    config = SandbagConfiguration(ram_used_bytes=waste_ram_bytes, cpu_used_portion=WASTE_CPU_PERCENT/100, cycle_size=10000)
#    m.send_request(AddComponent(ResourceWaster('sandbag', None, config)))

# creating instrument controller
    ims = InstrumentController('device_controller', None, None)
    m.send_request(AddComponent(ims), component_filter=component_id('AGENT'))

    # create consumer of data products
    transform_config = TransformConfiguration(transform_function=None) #(lambda input: dict(value=sum(input['value']))))
    transform_config.stats_interval = 60
    transform_config.report_stats = True
    transform = TransformComponent('consumer', None, transform_config)

    # get device IDs
    count=0
    for x in xrange(50):
        for dev in DEVICE_INFO:
            count+=1
            future = ans.expect_message()
            m.send_request(GetInstrumentId(dev[0]), component_filter=component_id('device_controller'))
            future.wait(timeout=30)
            msg = future.get()
            if msg.exception:
                raise msg.exception
            device_id = msg.result
            dev.append(device_id)
            transform_config.add_input(dev[1])
            transform_config.add_input(dev[2])
            print 'have id for device %s: %s' % (dev[0],device_id)
#    m.send_request(AddComponent(transform), component_filter=component_id('AGENT'))
#
#    # start devices
#    count=0


    sleep(3000)
    for count in xrange(len(DEVICE_INFO)):
        # alternate first 20 (port 4001) with last 20 (port 4002)
        index = count #(20 if count%2==0 else 0) + int(count/2)
        dev = DEVICE_INFO[index]

        m.send_request(StartDevice(dev[3]), component_filter=component_id('device_controller'))
        print 'starting device #' + str(count) + ': ' +dev[0]
        sleep(30)
        print 'device has been started'

        # log results as they arrive for a while
        wait_time=60 if count<QUICK_LOAD_DEVICES else 300
        end_time = time.time()+wait_time
        wait_interval=10 if count<QUICK_LOAD_DEVICES else 60
        while time.time()<end_time:
            now = time.localtime(time.time())
            values = perf.get_rate()
            print '%s: messages per minute: %f'%(time.asctime(now),values[1]*60/transform_config.stats_interval)
            sleep(wait_interval)

    sleep(1000)
        # get data product
#    future = ans.expect_message()
#    m.send_request(GetDataProduct(device_id), component_filter=component_id('device_controller'))
#    future.wait(timeout=30)
#    msg = future.get()
#    if msg.exception:
#        raise msg.exception
#    data_product_id = msg.result
#    print 'have data product id: ' + data_product_id

#    # start consumer
#    consumer = DataProductConsumer('consumer', None, ConsumerConfiguration('Gummi FCS Stream parsed 1', log_value=True))
#    m.send_request(AddComponent(consumer), component_filter=component_id('AGENT'))
#    m.send_request(StartRequest(), component_filter=component_id('consumer'))
#    print 'now consuming (check logs for CTD data)'




if __name__ == "__main__":
    main()
