
from pika import BlockingConnection, ConnectionParameters, PlainCredentials
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
    """ agent communications using a rabbitmq fanout channel """
    def __init__(self, config):
        self.config = config

    def _config(self, branch, node):
        if branch in self.config and node in self.config[branch]:
            return self.config[branch][node]
        else:
            return None

    def _get_connection(self):
        host = self._config('connector', 'hostname')
        if host:
            # using ape service broker configuration
            user = self._config('connector', 'username')
            log.info('using ape broker config host=%s user=%s', host, user)
            if user:
                passw = self._config('connector', 'password')
                credentials = PlainCredentials(user, passw)
                connection_config = ConnectionParameters(host=host, credentials=credentials)
                return BlockingConnection(connection_config)
            else:
                connection_config = ConnectionParameters(host=host)
                return BlockingConnection(connection_config)
        else:
            # using container broker configuration
            host = self._config('amqp', 'host')
            user = self._config('amqp', 'username')
            log.info('using container broker config host=%s user=%s', host, user)
            if user:
                passw = self._config('amqp', 'password')
                credentials = PlainCredentials(user, passw)
                connection_config = ConnectionParameters(host=host, credentials=credentials)
                return BlockingConnection(connection_config)
            else:
                connection_config = ConnectionParameters(host=host)
                return BlockingConnection(connection_config)

    def start_communication(self):
        self.connection = self._get_connection()
        self.in_channel = self.connection.channel()
        self.in_channel.exchange_declare(exchange=self._config('connector', 'inbound_exchange'), type='fanout')
        queue_declaration = self.in_channel.queue_declare(exclusive=True)
        queue_name = queue_declaration.method.queue
        self.in_channel.queue_bind(exchange=self._config('connector', 'inbound_exchange'), queue=queue_name)
        self.in_channel.basic_consume(self._on_message, queue=queue_name, no_ack=True)

        self.out_channel = self.connection.channel()
        self.out_channel.exchange_declare(exchange=self._config('connector', 'outbound_exchange'), type='fanout')
        log.debug("about to start consuming messages")
        self.in_channel.start_consuming()
    def stop_communication(self):
        self.in_channel.stop_consuming()
        self.connection.close()
    def send(self, result_message):
        self.out_channel.basic_publish(exchange=self._config('connector', 'outbound_exchange'), routing_key='', body=result_message.pack())
        log.debug('sent message')
    def _on_message(self, channel, method, properties, message):
        log.debug('received message')
        self.on_request(ApeRequestMessage().unpack(message))
