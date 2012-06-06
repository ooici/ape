
from pika import ConnectionParameters, PlainCredentials, SelectConnection, BlockingConnection
from ape.agent.connector_agent import BaseConnector, ConnectorDrivenAgent
from ape.common.messages import ApeRequestMessage
from pyon.util.log import log
from pika.reconnection_strategies import SimpleReconnectionStrategy

class AQMPConnector(BaseConnector):
    """ agent communications using a rabbitmq fanout channel """
    def __init__(self, config):
        """ config is a dictionary (presumably from Ion process startup)
            TODO: make caller extract relevant entries
                  instead of having to know where in Ion-specific dictionary to look
        """
        self.config = config

    def _config(self, *names):
        branch = self.config
        for name in names:
            if name in branch:
                branch = branch[name]
            else:
                return None
        return branch

    ### once _start_connection is called, the whole series of functions is invokes through pika callbacks;
    ### can treat the sequence as a single disjoint function call
    def _start_connection(self):
        log.debug('_get_connection')
        host = self._config('connector', 'hostname')
        srs = SimpleReconnectionStrategy()
        if host:
            # using ape service broker configuration
            port = self._config('connector', 'hostname')
            user = self._config('connector', 'username')
            log.debug('using ape broker config host=%s user=%s', host, user)
            if user:
                passw = self._config('connector', 'password')
                credentials = PlainCredentials(user, passw)
                connection_config = ConnectionParameters(host=host, port=port, credentials=credentials)
                return SelectConnection(connection_config, on_open_callback=self._on_connected)
            else:
                connection_config = ConnectionParameters(host=host, port=port)
                return SelectConnection(connection_config, on_open_callback=self._on_connected)
        else:
            # using container broker configuration
            host = self._config('server', 'amqp', 'host')
            user = self._config('server', 'amqp', 'username')
            port = self._config('server', 'amqp', 'port')
            log.debug('using container broker config host=%s port=%s user=%s', host, port, user)
            if user:
                passw = self._config('server', 'amqp', 'password')
                credentials = PlainCredentials(user, passw)
                connection_config = ConnectionParameters(host=host, port=port, credentials=credentials)
                return SelectConnection(connection_config, self._on_connected, reconnection_strategy=srs)
            else:
                connection_config = ConnectionParameters(host=host, port=port)
                return SelectConnection(connection_config, on_open_callback=self._on_connected)
    def _on_connected(self, connection):
        log.debug('_on_connected')
        connection.channel(self._on_inbound_channel_opened)
    def _on_inbound_channel_opened(self, channel):
        log.debug('_on_inbound_channel_opened')
        self.in_channel = channel
        self.in_channel.exchange_declare(exchange=self._config('connector', 'inbound_exchange'),
                                         type='fanout', callback=self._on_inbound_exchange_declared)
    def _on_inbound_exchange_declared(self, exchange):
        log.debug('_on_inbound_exchange_declared')
        self.in_channel.queue_declare(exclusive=True, callback=self._on_inbound_queue_declared)
    def _on_inbound_queue_declared(self, queue_declaration):
        log.debug('_on_inbound_queue_declared')
        self._queue_name = queue_declaration.method.queue
        self.in_channel.queue_bind(exchange=self._config('connector', 'inbound_exchange'), queue=self._queue_name, callback=self._on_inbound_bind)
    def _on_inbound_bind(self, arg):
        log.debug('_on_inbound_bind')
        self.connection.channel(self._on_outbound_channel_opened)
    def _on_outbound_channel_opened(self, channel):
        log.debug('_on_outbound_channel_opened')
        self.out_channel = channel
        self.out_channel.exchange_declare(exchange=self._config('connector', 'outbound_exchange'), type='fanout', callback=self._on_outbound_exchange)
    def _on_outbound_exchange(self, exchange):
        log.debug('_on_outbound_exchange')
        self.in_channel.basic_consume(self._on_message, queue=self._queue_name, no_ack=True)
        log.info('ape is now consuming messages')
    ### end of sequence of callbacks begun with _start_connection

    def start_communication(self):
        log.debug('start_communication')
        self.connection = self._start_connection()
        self.connection.ioloop.start()

    def stop_communication(self):
        self.in_channel.stop_consuming()
        self.connection.close()

    def send(self, result_message):
        self.out_channel.basic_publish(exchange=self._config('connector', 'outbound_exchange'), routing_key='', body=result_message.pack())
        log.debug('sent message')

    def _on_message(self, channel, method, properties, message):
        log.debug('received message')
        self.on_request(ApeRequestMessage().unpack(message))
