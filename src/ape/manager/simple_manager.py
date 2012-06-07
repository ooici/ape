
from pika import PlainCredentials, ConnectionParameters, SelectConnection
from ape.common.messages import ApeRequestMessage, ApeResultMessage, ALL_AGENTS
from ape.common.types import ApeRequest, ApeException
import ape.common.requests
from ape.apelog import log
from ape.common.requests import InventoryResult
from threading import Thread
from time import sleep
from pika.reconnection_strategies import SimpleReconnectionStrategy

outbound_exchange='ape-requests'
inbound_exchange='ape-results'

class _ExecBlocking(Thread):
    def __init__(self, connection):
        self.connection = connection
        super(_ExecBlocking,self).__init__()
    def run(self):
        self.connection.ioloop.start()

class Listener(object):
    def on_message(self, message):
        pass

class InventoryListener(Listener):
    def __init__(self):
        self.inventory = {}
    def on_message(self, message):
        if isinstance(message.result, InventoryResult):
            self.inventory[message.agent] = message.result

class SimpleManager(object):
    """ simple manager that lets you send requests and view results """
    def __init__(self, broker_hostname='localhost', broker_username='guest', broker_password='guest'):
        log.debug('starting manager: broker=%s user=%s', broker_hostname, broker_username)
        self.listeners = []
        self._initializing = True
        if broker_username:
            credentials = PlainCredentials(broker_username, broker_password) if broker_username else None
            self.connection = SelectConnection(ConnectionParameters(host=broker_hostname, credentials=credentials), self._on_connected, reconnection_strategy=SimpleReconnectionStrategy())
        else:
            p = ConnectionParameters(host=broker_hostname)
            s = SimpleReconnectionStrategy()
            self.connection = SelectConnection(p, on_open_callback=self._on_connected, reconnection_strategy=s)
        _ExecBlocking(self.connection).start()
        while self._initializing:
            sleep(1)
    def _on_connected(self, connection):
        self.connection.channel(self._on_outbound_channel)
    def _on_outbound_channel(self, channel):
        self.outbound_channel = channel
        self.outbound_channel.exchange_declare(exchange=outbound_exchange, type='fanout',callback=self._on_outbound_exchange)
    def _on_outbound_exchange(self, arg):
        self.connection.channel(self._on_inbound_channel)
    def _on_inbound_channel(self, channel):
        self.inbound_channel = channel
        channel.exchange_declare(exchange=inbound_exchange, type='fanout', callback=self._on_inbound_exchange)
    def _on_inbound_exchange(self, arg):
        self.inbound_channel.queue_declare(exclusive=True, callback=self._on_inbound_queue)
    def _on_inbound_queue(self, queue_declaration):
        self.queue_name = queue_declaration.method.queue
        self.inbound_channel.queue_bind(exchange=inbound_exchange, queue=self.queue_name, callback=self._on_queue_bound)
    def _on_queue_bound(self, arg):
        self.inbound_channel.basic_consume(self.callback, queue=self.queue_name, no_ack=True, consumer_tag=inbound_exchange)
        self._initializing = False

    def add_listener(self, listener):
        assert isinstance(listener, Listener)
        self.listeners.append(listener)

    def callback(self, ch, method, properties, body):
        message = ApeResultMessage().unpack(body)
        [ l.on_message(message) for l in self.listeners ]

    def send_request(self, request, agent_filter=ALL_AGENTS, component_filter=None):
        if isinstance(request, ApeRequestMessage):
            message = request
        elif isinstance(request, ApeRequest):
            message = ApeRequestMessage(request=request, agent_filter=agent_filter, component_filter=component_filter)
        else:
            raise ApeException("don't know how to send type: " + str(type(request)))
        self.outbound_channel.basic_publish(exchange=outbound_exchange, routing_key='', body=message.pack())

    def close(self):
        # TODO: these either hang or log exceptions!  how to close cleanly?
#        self.inbound_channel.basic_cancel(inbound_exchange)
#        self.outbound_channel.close()
#        self.inbound_channel.stop_consuming()
#        self.inbound_channel.close()
        self.connection.close()
        pass
