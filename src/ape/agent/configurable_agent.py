''' PyonApeAgent that is configured using the deploy.yml process configuration '''

from ape.agent.aqmp_connector import AQMPConnector
from ape.agent.connector_agent import ConnectorDrivenAgent
from ape.common.types import ApeException
from ape.component.instrument_simulator import InstrumentSimulator

PROPERTY_NAMES = ('role')

class ConfigurableAgent(ConnectorDrivenAgent):
    def on_start(self):
        ''' when container starts process, use configuration to create connector '''
        type = self.CFG.get_safe('connector.type')
        if type != 'AQMPConnector':
            raise ApeException('do not know how to use connector type: ' + type)
        self.connector = AQMPConnector(self.CFG)
        self.agent_id = self.CFG.get('agent_id') or self.id
        for name in PROPERTY_NAMES:
            value = self.CFG.get(name)
            if value:
                self.properties[name] = value
        super(ConfigurableAgent,self).on_start()
