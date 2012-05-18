''' agent that can be run as a pycc process

    NOTE: implementing subclass is expected to set PyonApeAgent.agent_id to a system-wide unique string
'''

from ape.common.types import BaseApeAgent
from ape.common.requests import PingRequest, PingResult, AddComponent, InventoryResult, InventoryRequest
from pyon.ion.process import StandaloneProcess
from pyon.util.log import log
from threading import Thread
from traceback import format_exc
from pyon.util.log import log

from ape.component.instrument_simulator import InstrumentSimulator

class _ExecutionThread(Thread):
    def __init__(self, agent):
        self.agent = agent
        super(_ExecutionThread,self).__init__()
    def run(self):
        log.debug(self.agent.__class__.__name__ + " <" + self.agent.agent_id + "> running")
        try:
            self.agent.manage()
        except Exception:
            log.error("agent exception: " + format_exc())
        else:
            log.debug("agent shutting down")
    def kill(self):
        self.join()

class PyonApeAgent(StandaloneProcess,BaseApeAgent):
    def __init__(self):
        self.thread = _ExecutionThread(self)
        self.components = {} # component id -> component
        self.properties = {} # name -> value for agent filters
        self.inventory = {}  # component id -> type name
        self.keep_running = True
        super(PyonApeAgent,self).__init__()
    def on_init(self):
        pass
    def on_start(self):
        self.start_agent()
    def on_quit(self):
        log.debug('on_quit called')
        if self.keep_running:
            self.stop_agent()
    def on_stop(self):
        log.debug('on_stop called')
        if self.keep_running:
            self.stop_agent()

    def start_agent(self):
        log.debug('start_agent called')
        self.add_component('AGENT', self)
        self.thread.start()
    def stop_agent(self):
        self.keep_running = False
        self.thread.kill()
        for component in self.components.itervalues():
            component.stop_component()
        super(PyonApeAgent,self).on_quit()
    def add_component(self, component_id, component):
        ''' subclass should add_components created to make sure they can be shutdown from on_quit '''
        if self.components.has_key(component_id):
            raise Exception('attempt to register two components with same id: ' + component_id)
        component.agent = self
#        self.components[component_id] = component ---> don't add unless start_component() succeeds
        component.start_component()
        self.components[component_id] = component
        self.inventory[component_id] = component.__class__.__name__
    def invoke_action(self, component_id, request):
        log.debug('performing: ' + str(request))
        component = self.components[component_id]
        try:
            component.perform_action(request)
        except Exception as ex:
            log.error('request failed: ' + str(request) + '\nexception: ' + str(ex) + '\nstack trace: ' + format_exc())
        log.debug('completed: ' + str(request))

    def perform_action(self, request):
        if isinstance(request, PingRequest):
            self.report('AGENT', PingResult())
        elif isinstance(request, AddComponent):
            self.add_component(request.component.component_id, request.component)
        elif isinstance(request, InventoryRequest):
            self.report('AGENT', InventoryResult(self.properties, self.inventory))
            log.debug('properties: ' + repr(self.properties) + '\ninventory: ' + repr(self.inventory))
        else:
            log.info('action not performed: ' + request.__class__.__name__)

    def manage(self):
        ''' subclass should perform operations on components '''
        log.debug("Nothing to do!")
