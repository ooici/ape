''' resource-eating deadweight

    used to put system under artificial load.

    keep CPU busy some portion of the time (0=never, 1=always)
    and use some # bytes of RAM
'''
from threading import Thread
from ape.common.requests import ChangeConfiguration
from ape.common.types import ApeComponent
from time import time, sleep
import random
from pyon.public import log

class Configuration(object):
    def __init__(self, ram_used_bytes=0, cpu_used_portion=0, cycle_size=100):
        ''' configuration for resources to be wasted

            bytes of RAM,
            portion of time to spend in calculations vs idle,
            number of calculations per sleep cycle (keep small)

            NOTE: cpu usage metric is not quite %cpu, although comparable
                because the calculations may not use 100% cpu time,
                and the sleep time is not guaranteed
                 (the system may wait longer to return to the next calculation)
        '''
        self.ram_used = ram_used_bytes
        self.cpu_usage = cpu_used_portion
        self.cycle_size = cycle_size

class ResourceWaster(ApeComponent):

    def _start(self):
        self._use_ram()
        self.thread = _CpuWaster(self)
        self.thread.start()
    def _stop(self):
        self.thread.keep_running = False

    def perform_action(self, request):
        if isinstance(request, ChangeConfiguration):
            self.configuration = request.configuration
            self._use_ram()
    def _use_ram(self):
        self.wasted_ram = 'a' * max(self.configuration.ram_used, 200) # must have string for random choice
        log.debug('using %d bytes ram' % len(self.wasted_ram))

class _CpuWaster(Thread):
    def __init__(self, waster):
        self.waster = waster
        self.keep_running = True
        super(_CpuWaster, self).__init__()

    def run(self):
        while self.keep_running:
            start = time()
            self.calculateSomething()
            end = time()
            remaining = (end-start)/self.waster.configuration.cpu_usage
            sleep(remaining)

    def calculateSomething(self):
        for count in xrange(self.waster.configuration.cycle_size):
            random.gammavariate(.5, 3)
            random.choice(self.waster.wasted_ram) # keep in RAM, don't let memory get stale and page out
