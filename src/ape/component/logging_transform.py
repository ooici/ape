
'''
silly little transform to consume granules and log message rates

can consume any data product to report how quickly granules were produced by that data product.
default is to log time elapsed per 100 granules (configurable).
if an ape agent is found running in the same container, will also send a PerformanceResult message.
'''

from ion.core.process.transform import TransformDataProcess
from ooi.logging import log
import threading
import time
from ape.common.requests import PerformanceResult

APE_AGENT_NAME='testing_agent'

class LoggingTransform(TransformDataProcess):
    def __init__(self,*a,**b):
        super(LoggingTransform,self).__init__(*a,**b)
        self._count_lock = threading.Lock()
        self._report_lock = threading.Lock()
        self._count = 0

    def on_start(self):
        super(LoggingTransform,self).on_start()
        self._label = self.CFG.get('label', 'rate_' + self._proc_name)
        self._next = self._rate = self.CFG.get('rate', 100)
        self._start = time.time()
        try:
            agent_name = self.CFG.get('ape_agent', APE_AGENT_NAME)
            self._agent = self.container.proc_manager.procs_by_name[agent_name]
        except:
            log.warn('can not send reply messages, no ape agent found in container: %s', agent_name)
            self._agent = None

    def recv_packet(self, packet, stream_route, stream_id):
        log.trace("received granule: %r from stream %r", packet, stream_id)
        n = self.increment_count()
        if n > self._next:
            with self._report_lock:
                self._next += self._rate
                end = time.time()
                elapsed = end-self._start
                self._start = end
                self.report(elapsed)

    def report(self, elapsed):
        log.info('received %d messages in %d seconds', self._rate, elapsed)
        if self._agent:
            self._agent.report(self._label, PerformanceResult(elapsed))

    def increment_count(self):
        with self._count_lock:
            self._count += 1
            return self._count