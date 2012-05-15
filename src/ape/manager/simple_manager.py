
import pika
from ape.common.messages import ApeRequestMessage, ApeResultMessage, ALL_AGENTS
from ape.common.types import ApeRequest, ApeException
import ape.common.requests
from ape.common.requests import InventoryResult
from threading import Thread
from time import sleep

outbound_exchange='ape-requests'
inbound_exchange='ape-results'

class _ExecBlocking(Thread):
    def __init__(self, inbound_channel):
        self.inbound_channel = inbound_channel
        super(_ExecBlocking,self).__init__()
    def run(self):
        print 'about to start consuming'
        self.inbound_channel.start_consuming()
        print 'start_consuming completed'

class SimpleManager(object):
    ''' simple manager that lets you send requests and view results '''
    def __init__(self):
        self.inventory = dict()
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
        self.outbound_channel = self.connection.channel()
        self.outbound_channel.exchange_declare(exchange=outbound_exchange, type='fanout')

        self.inbound_channel = self.connection.channel()
        self.inbound_channel.exchange_declare(exchange=inbound_exchange, type='fanout')
        queue_name = self.inbound_channel.queue_declare(exclusive=True).method.queue
#        result = self.inbound_channel.queue_declare(exclusive=True)
#        queue_name = result.method.queue
        self.inbound_channel.queue_bind(exchange=inbound_exchange, queue=queue_name)
        self.inbound_channel.basic_consume(self.callback, queue=queue_name, no_ack=True, consumer_tag=inbound_exchange)

        self.thread = _ExecBlocking(self.inbound_channel)
        self.thread.setDaemon(True)
        self.thread.start()
        sleep(5) # give channel time to start
        print 'should be consuming now'
    def callback(self, ch, method, properties, body):
        print 'unpacking'
        message = ApeResultMessage().unpack(body)
        print "%s %s:\t%s" % (message.agent, message.component, repr(message.result))
        if isinstance(message.result, InventoryResult):
            self.inventory[message.agent] = message.result
    def send_request(self, request, agent_filter=ALL_AGENTS, component_filter=None):
        if isinstance(request, ApeRequestMessage):
            message = request
        elif isinstance(request, ApeRequest):
            message = ApeRequestMessage(request=request, agent_filter=agent_filter, component_filter=component_filter)
        else:
            raise ApeException("don't know how to send type: " + str(type(request)))
        self.outbound_channel.basic_publish(exchange=outbound_exchange, routing_key='', body=message.pack())
    def close(self):
#        self.inbound_channel.basic_cancel(inbound_exchange)
#        self.outbound_channel.close()
#        self.inbound_channel.stop_consuming()
#        self.inbound_channel.close()
#        self.connection.close()
        pass
