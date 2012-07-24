"""
component to put load on the couch db from within the container

this component makes direct DB calls instead of using the pycc couchdb interface
"""
import random
import string
from threading import Thread
import time
import traceback
from gevent.event import AsyncResult
from pika.adapters.select_connection import SelectConnection
from pika.connection import ConnectionParameters
from pika.credentials import PlainCredentials
from pika.reconnection_strategies import SimpleReconnectionStrategy
from pyon.util.log import log
from pyon.core.bootstrap import CFG
from ape.common.requests import StartRequest, StopRequest, ChangeConfiguration, PerformanceResult
from ape.common.types import ApeComponent, ApeException, ApeRequest
import couchdb
from pyon.datastore.id_factory import SaltedTimeIDFactory, RandomIDFactory

class Configuration(object):

    sleep_between_operations = 0
    sleep_between_cycles = 0
    sleep_between_reports = 30

    message_count = 100
    message_size = 100

    def __init__(self, exchange):
        self.exchange = exchange

CHARS=string.printable
def random_string(length):
    return ''.join(random.choice(CHARS) for x in range(length))

class MessageProducer(ApeComponent):
    def _start(self):
        self.thread = _ProducerThread(self.configuration, self.agent.container)
        self.thread.start()
        self.reporter = _ReportingThread(self.configuration, self, self.thread)
        self.reporter.start()

    def _stop(self):
        self.reporter.shutdown()
        self.thread.shutdown()
        self.thread = None

    def perform_action(self, request):
        if isinstance(request, StartRequest):
            self.thread.set_enabled(True)
            self.reporter.set_enabled(True)
        elif isinstance(request, StopRequest):
            self.reporter.set_enabled(False)
            self.thread.set_enabled(False)
        elif isinstance(request, ChangeConfiguration):
            self.thread.set_config(request.configuration)
        else:
            raise ApeException('message producer does not know how to: ' + str(request))

class _BaseThread(Thread):
    def __init__(self,config, container):
        super(_BaseThread,self).__init__()
        self.config = config
        self.container = container
        self.enabled = False
        self.shutdown = False
        self.reset_metrics()
        self._connect()

    def _connect(self):
        self.connected = AsyncResult()
        self.connection = self._start_connection()
        self.connection.ioloop.start()
        self.connected.wait()
        log.info('connected')
    def _disconnect(self):
        self.channel.close()
        self.connection.close()
        self.channel = None
        self.connection = None

    ### sequence of callbacks establishing mq connection
    def _start_connection(self):
        host = CFG.server.amqp.host
        port = CFG.server.amqp.port
        username = CFG.server.amqp.username
        password = CFG.server.amqp.password
        log.debug('_start_connection')
        srs = SimpleReconnectionStrategy()
        if username:
            credentials = PlainCredentials(username, password)
            connection_config = ConnectionParameters(host=host, port=port, credentials=credentials)
            return SelectConnection(connection_config, on_open_callback=self._on_connected, reconnection_strategy=srs)
        else:
            connection_config = ConnectionParameters(host=host, port=port)
            return SelectConnection(connection_config, on_open_callback=self._on_connected, reconnection_strategy=srs)
    def _on_connected(self, connection):
        log.debug('_on_connected')
        self.connection.channel(self._on_channel_opened)
    def _on_channel_opened(self, channel):
        log.debug('_on_channel_opened')
        self.channel = channel
        channel.exchange_declare(exchange=self.config.exchange, type='fanout', callback=self._on_exchange)
    def _on_exchange(self):
        raise ApeException('should be implemented by subclass!')
    ### producer and consumer threads continue with additional callbacks, eventually finishing with self.connected.set()

    def set_config(self, config):
        self._disconnect()
        self.config = config
        self._connect()
    def set_enabled(self, is_enabled):
        if is_enabled:
            self.reset_metrics()
        self.enabled = is_enabled
    def shutdown(self):
        self.shutdown = True
        self.db = None # cause operations to throw exception, exit cycle faster

    def perform_iteration(self):
        raise ApeException('should be implemented by subclass!')

    def run(self):
        while not self.shutdown:
            if self.enabled:
                self.perform_iteration()
                time.sleep(self.config.sleep_between_cycles)
            else:
                time.sleep(max(1,self.config.sleep_between_cycles))
        self.channel.close()
        self.connection.close()

    def reset_metrics(self):
        self.start_time = time.time()
        self.operations = 0

    def get_report(self):
        elapsed = time.time() - self.start_time
        return { 'elapsed': elapsed,
                 'operations': self.operations }

class _ProducerThread(_BaseThread):
    def _on_exchange(self, exchange):
        log.debug('_on_exchange')
        self.connected.set()
    def send(self, message):
        self.channel.basic_publish(exchange=self.config.exchange, routing_key='', body=message)
    def perform_iteration(self):
        """perform configured number of each operation in random order"""
        for x in xrange(self.config.message_count):
            try:
                self.send(random_string(self.config.message_length))
                self.operations+=1
            except Exception:
                if self.shutdown:
                    return
                log.info('send operation failed: %s' % traceback.format_exc())
            time.sleep(self.config.sleep_between_operations)

class _ConsumerThread(_BaseThread):
    def _on_exchange(self, exchange):
        log.debug('_on_exchange')
        self.channel.queue_declare(exclusive=True, callback=self._on_queue_declared)
    def _on_queue_declared(self, queue_declaration):
        log.debug('_on_queue_declared')
        self._queue_name = queue_declaration.method.queue
        self.channel.queue_bind(exchange=self.config.exchange, queue=self._queue_name, callback=self._on_queue_bind)
    def _on_queue_bind(self, arg):
        log.debug('_on_queue_bind')
        self.channel.basic_consume(self._on_message, queue=self._queue_name, no_ack=True)
        self.connected.set()
    def _on_message(self, channel, method, properties, message):
        self.operations+=1
        time.sleep(self.config.sleep_between_operations)
    def perform_iteration(self):
        pass

class _ReportingThread(Thread):
    def __init__(self, config, component, target):
        super(_ReportingThread,self).__init__()
        self.config = config
        self.component = component
        self.target = target
        self.shutdown = False
        self.enabled = False

    def set_enabled(self, is_enabled):
        self.enabled = is_enabled
    def shutdown(self):
        self.shutdown = True

    def run(self):
        while not self.shutdown:
            if self.enabled:
                time.sleep(self.config.sleep_between_reports)
                self.report_status()
            else:
                time.sleep(max(1,self.config.sleep_between_reports))

    def report_status(self):
        report = self.target.get_report()
        message = PerformanceResult(report)
        self.component.report(message)
