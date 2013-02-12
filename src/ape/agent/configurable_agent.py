''' PyonApeAgent that is configured using the deploy.yml process configuration '''

from ape.agent.aqmp_connector import AQMPConnector
from ape.agent.connector_agent import ConnectorDrivenAgent
from ape.common.types import ApeException
from pyon.core import bootstrap
from ooi.logging import log

PROPERTY_NAMES = ('role')

class ConfigurableAgent(ConnectorDrivenAgent):
    def on_start(self):
        ''' when container starts process, use configuration to create connector '''
        type = self.CFG.get_safe('connector.type')
        if type != 'AQMPConnector':
            raise ApeException('do not know how to use connector type: ' + type)
        config = {}
        config.update(bootstrap.CFG)
        config.update(self.CFG)
        self.connector = AQMPConnector(config)
        self.agent_id = self.CFG.get('unique_id') or self.id
        log.info('ape agent id: %s', self.agent_id)
        for name in PROPERTY_NAMES:
            value = self.CFG.get(name)
            if value:
                self.properties[name] = value
        super(ConfigurableAgent,self).on_start()
