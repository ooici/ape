
from ape.common.types import ApeRequest, ApeResult
import logging

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

# operate on sandbags
class ChangeConfiguration(ApeRequest):
    def __init__(self, configuration):
        self.configuration = configuration

class PerformanceResult(ApeResult):
    def __init__(self, data):
        self.data = data

def getResult(function, *a, **b):
    try:
        result = function(*a, **b)
        return OperationResult(result=result)
    except Exception,e:
        logging.warn('operation failed with exception', exc_info=True)
        return OperationResult(exception=e)

class OperationResult(ApeResult):
    def __init__(self, result=None, exception=None):
        self.result = result
        self.exception = exception
