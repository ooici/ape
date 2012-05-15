
from pika import BlockingConnection, ConnectionParameters
from ape.agent.connector_agent import BaseConnector, ConnectorDrivenAgent
from ape.common.messages import ApeRequestMessage
from pyon.util.log import log

# TODO: get configuration from IonProcess startup configuration
class Config(object):
    inbound_exchange = 'ape-requests'
    outbound_exchange = 'ape-results'
    def get_connection_parameters(self):
        return ConnectionParameters(host='localhost')

class AQMPConnector(BaseConnector):
    ''' agent communications using a rabbitmq fanout channel '''
    def __init__(self, config):
        self.config = config
    def start_communication(self):
        connection_config = ConnectionParameters(host=self.config.get('hostname'))
        self.connection = BlockingConnection(connection_config)

        self.in_channel = self.connection.channel()
        self.in_channel.exchange_declare(exchange=self.config.get('inbound_exchange'), type='fanout')
        queue_declaration = self.in_channel.queue_declare(exclusive=True)
        queue_name = queue_declaration.method.queue
        self.in_channel.queue_bind(exchange=self.config.get('inbound_exchange'), queue=queue_name)
        self.in_channel.basic_consume(self._on_message, queue=queue_name, no_ack=True)

        self.out_channel = self.connection.channel()
        self.out_channel.exchange_declare(exchange=self.config.get('outbound_exchange'), type='fanout')
        log.debug("about to start consuming messages")
        self.in_channel.start_consuming()
    def stop_communication(self):
        self.in_channel.stop_consuming()
        self.connection.close()
    def send(self, result_message):
        self.out_channel.basic_publish(exchange=self.config.get('outbound_exchange'), routing_key='', body=result_message.pack())
        log.debug('sent message')
    def _on_message(self, channel, method, properties, message):
        log.debug('received message')
        self.on_request(ApeRequestMessage().unpack(message))

class AQMPAgent(ConnectorDrivenAgent):
    def __init__(self):
        # TODO: get config parameters from process startup yml config
        config = { 'inbound_exchange': 'ape-requests', 'outbound_exchange': 'ape-results', 'hostname': 'localhost'}
        self.connector = FanoutAQMPConnector(config)
        self.agent_id = 'UNIQUE_ID'
        ConnectorDrivenAgent.__init__(self)
