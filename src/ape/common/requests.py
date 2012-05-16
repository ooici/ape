
from ape.common.types import ApeRequest, ApeResult

# operate on ape.agent.pyon_process.PyonApeAgent
class PingRequest(ApeRequest): pass
class PingResult(ApeResult): pass
class InventoryRequest(ApeRequest): pass
class InventoryResult(ApeResult):
    def __init__(self, properties, components):
        self.properties = properties
        self.components = components
    def __str__(self):
        return 'properties: ' + repr(self.properties) + '\ncomponents: ' + repr(self.components)

class AddComponent(ApeRequest):
    def __init__(self, component):
        self.component = component

# operate on ape.component.instrument_simulator.InstrumentSimulator
class StartRequest(ApeRequest): pass
class StopRequest(ApeRequest): pass
class RegisterWithContainer(ApeRequest): pass
class UnregisterInstrument(ApeRequest): pass

class PerformanceResult(ApeResult):
    def __init__(self, data):
        self.data = data
#
#class RegistryLookup(ApeRequest):
#    def __init__(self,