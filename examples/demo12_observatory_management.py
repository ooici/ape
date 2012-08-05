"""
ape sample: observatory management

test components that connect to service gateway and control device agents
"""

import gevent.monkey
from interface.services.coi.iresource_registry_service import ResourceRegistryServiceClient
from interface.services.dm.itransform_management_service import TransformManagementServiceClient

gevent.monkey.patch_all(aggressive=False)

from ape.manager.simple_manager import SimpleManager, InventoryListener, Listener
from ape.common.requests import PingRequest, AddComponent, StartRequest, InventoryRequest, StopRequest, PerformanceResult, ChangeConfiguration
from ape.component.instrument_simulator import InstrumentSimulator
from ape.component.instrument_simulator import Configuration as InstrumentConfiguration
from ape.component.consumer import DataProductConsumer
from ape.component.consumer import Configuration as ConsumerConfiguration
from ape.component.sandbag import Configuration as SandbagConfiguration, ResourceWaster
from ape.common.messages import  component_id, agent_id, component_type
from time import sleep
import math

class PerformanceListener(Listener):
    resource_registry = ResourceRegistryServiceClient(node=self.agent.container.node)
    transform_management = TransformManagementServiceClient(node=self.agent.container.node)

    def __init__(self):
        self.latest_data = {}
        self.known_components = []
    def add_component(self, component_id):
        self.known_components.append(component_id)
    def on_message(self, message):
        if isinstance(message.result, PerformanceResult):
            self.latest_data[message.agent] = message.result
            print 'update: rate=' + str(self.get_rate()) + ' msgs/sec'
    def get_rate(self):
        iterations_per_second = 0.
        for v in self.latest_data.itervalues():
            iterations_per_second += v.data['count']/v.data['time']
        return iterations_per_second

def wait(a):
    raw_input('--- press enter to continue ---')
#    sleep(a)

def main():
    m = SimpleManager()

    print 'performance with no sandbags'
    sleep(20)

    print 'starting 1gb memory usage, 10% cpu'
    config = SandbagConfiguration(ram_used_bytes=1000000000, cpu_used_portion=.1)
    m.send_request(AddComponent(ResourceWaster('sandbag', None, config)))
    sleep(30)

    print 'starting 100k memory usage, 70% cpu'
    config = SandbagConfiguration(ram_used_bytes=1000000, cpu_used_portion=.7)
    m.send_request(ChangeConfiguration(config), component_filter=component_id('sandbag'))
    sleep(30)

if __name__ == "__main__":
    main()
