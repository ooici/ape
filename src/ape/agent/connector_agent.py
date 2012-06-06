''' ChannelAgent executes commands received from an external source.

    the source is abstract, defined by subclassing ChannelCommunicator.
'''

from ape.agent.pyon_process import PyonApeAgent
from ape.common.types import ApeComponent, ApeRequest, ApeResult
from ape.common.messages import ApeResultMessage, filter_applies
from pyon.util.log import log

class BaseConnector(object):
    ''' base class for defining pluggable methods of communication between manager and agent '''
    def set_agent(self, agent):
        ''' define the agent to alert when a request message arrives '''
        self.agent = agent
    def start_communication(self):
        ''' begin receiving requests and passing responses '''
        pass
    def stop_communication(self):
        ''' stop receiving requests and passing responses '''
        pass
    def send(self, result_message):
        pass
    def on_request(self, request_message):
        ''' _receive should be called by implementing subclass when a message is received from the manager '''
        if filter_applies(self.agent, request_message.agent_filter):
            self.agent.on_message(request_message)

class ConnectorDrivenAgent(PyonApeAgent,ApeComponent):
    ''' agent that acts on operations received from an external source.
        it also acts as a component itself for certain operations -- like starting new components.

        connector and agent_id attributes must be set by subclass prior to start_agent being called
    '''
    def __init__(self):
        PyonApeAgent.__init__(self)
        ApeComponent.__init__(self, 'AGENT', self, None)
    def start_agent(self):
        ''' get endpoints to communicate with manager '''
        self.connector.set_agent(self)
#        super(PyonApeAgent,self).start_agent() ---> parent of PyonApeAgent called, ie- super(super())
#        super(ChannelCommunicator,self).start_agent() ---> ERROR: cannot load class
        PyonApeAgent.start_agent(self) ## ugly, but invokes correct superclass
    def manage(self):
        ''' start listening to endpoint for new messages from manager '''
        self.connector.start_communication()

    def stop_agent(self):
        ''' close endpoints '''
        self.connector.stop_communication()
        super(PyonApeAgent,self).stop_agent()

    def report(self, component_id, result):
        ''' send result to manager '''
        log.debug('sending result message: ' + component_id + ', ' + result.__class__.__name__)
        self.connector.send(ApeResultMessage(self.agent_id, component_id, result))

    def on_message(self, request_message):
        ''' invoked by connector when a message arrives '''
        if filter_applies(self, request_message.agent_filter):
            for component in self.components.values():
                applies = filter_applies(component, request_message.component_filter)
#                log.debug('testing filter against component: ' + component.component_id + ': ' + repr(applies))
                if applies:
                    self.invoke_action(component.component_id, request_message.request)
