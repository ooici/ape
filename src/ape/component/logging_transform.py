
'''
silly little transform to consume granules and log rates
'''

from ion.core.process.transform import TransformDataProcess
from ooi.logging import log
import threading
import time

class LoggingTransform(TransformDataProcess):
    def __init__(self,*a,**b):
        super(LoggingTransform,self).__init__(*a,**b)
        self.count_lock = threading.Lock()
        self.report_lock = threading.Lock()
        self.count = 0
        self.next = self.rate = 100 # make configurable?
        self.start = time.time()

    def recv_packet(self, packet, stream_route, stream_id):
        log.trace("received granule: %r from stream %r", packet, stream_id)
        n = self.increment_count()
        if n > self.next:
            with self.report_lock:
                self.next += self.rate
                end = time.time()
                elapsed = end-self.start
                self.start = end
                log.info('received %d messages in %d seconds', self.rate, elapsed)

    def increment_count(self):
        with self.count_lock:
            self.count += 1
            return self.count