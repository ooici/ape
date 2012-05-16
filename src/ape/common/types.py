''' define base classes used for ape testing framework '''
#from pyon.util.log import log

class BaseApeAgent(object):
    ''' base agent type '''
    agent_id = None
    def __init__(self):
        pass
    def start_agent(self):
        ''' lifecycle method: start listening to manager '''
        #        log.debug('base start_agent called')
        pass
    def report(self, component_id, result):
        ''' report results back to manager (callback by component) '''
        pass
    def stop_agent(self):
        ''' release resources, stop all components, shutdown '''
        pass

class ApeComponent(object):
    ''' base component type '''
    def __init__(self, component_id, agent, configuration):
        self.component_id = component_id
        self.agent = agent
        self.configuration = configuration
        self.was_started = False
        self.was_stopped = False
    def _start(self):
        pass
    def start_component(self):
        if self.was_started:
            raise Exception("lifecycle error -- can only start component once")
        self._start()
    def perform_action(self, request):
        pass
    def report(self, results):
        self.agent.report(self.component_id, results)
    def _stop(self):
        pass
    def stop_component(self):
        ''' release any resources, stop reporting results, shutdown '''
        self.was_stopped = True
        self._stop()
        pass
    def fail(self, exception):
        self.report(exception)
        self.stop()

class ApeException(Exception):
    pass

class ApeRequest(object):
    def __str__(self):
        return self.__class__.__name__

class ApeResult(object):
    def __str__(self):
        return self.__class__.__name__


