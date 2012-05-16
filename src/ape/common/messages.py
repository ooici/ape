
import ape.common  # make sure to have all the types pickle may need!
import pickle

from ape.common.types import ApeComponent, BaseApeAgent

class ApeMessage(object):
    def pack(self):
        return pickle.dumps(self)
    def unpack(self, string_representation):
        return pickle.loads(string_representation)


ALL_AGENTS = {}

class ApeRequestMessage(ApeMessage):
    ''' message from manager to one or more agents '''
    def __init__(self, agent_filter=ALL_AGENTS, component_filter=None, request=None):
        self.agent_filter = agent_filter
        self.component_filter = component_filter
        self.request = request

class ApeResultMessage(ApeMessage):
    ''' message from an agent to the manager '''
    def __init__(self, agent_id=None, component_id=None, result=None):
        self.agent = agent_id
        self.component = component_id
        self.result = result

def host_name(value):
    ''' agent filter: match based on hostname '''
    return { 'hostname': value }

def agent_id(value):
    ''' agent filter: match based on unique agent ID from config file '''
    return { 'agent_id': value }

def host_service(value):
    ''' agent filter: match based on system role (db, aqmp, cc, etc)
        note: one system may provide more than one of these services
    '''
    return { 'role': value }

def container_agents(value):
    ''' agent filter: match agents running within a capability container '''
    return { 'in_container': value }

def container_service(value):
    ''' agent filter: match container agents where container is running this service '''
    return { 'service': value }

def component_type(value):
    ''' component filter: match components of given type '''
    return { 'type': value }

def component_id(value):
    ''' component filter: specific component with given id '''
    return { 'component_id': value }


def filter_applies(obj, filter):
    if filter is None:
        return True
    if filter.get('component_id') and obj.component_id != filter.get('component_id'):
        return False
    if filter.get('agent_id') and isinstance(obj, BaseApeAgent) and obj.agent_id != filter.get('agent_id'):
        return False
    if filter.get('type'):
        if not obj.__class__.__name__==filter.get('type') and not isinstance(obj, filter.get('type')):
            return False
    return True