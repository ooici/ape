
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
        self._count_lock = threading.Lock()
        self._report_lock = threading.Lock()
        self._count = 0
        self._next = self._rate = 100 # make configurable?
        self._start = time.time()

    def recv_packet(self, packet, stream_route, stream_id):
        log.trace("received granule: %r from stream %r", packet, stream_id)
        n = self.increment_count()
        if n > self._next:
            with self._report_lock:
                self._next += self._rate
                end = time.time()
                elapsed = end-self._start
                self._start = end
                log.info('received %d messages in %d seconds', self._rate, elapsed)

    def increment_count(self):
        with self._count_lock:
            self._count += 1
            return self._count