
'''
silly little transform to consume granules and log rates
'''

from ion.core.process.transform import TransformDataProcess
from ooi.logging import log

class LoggingTransform(TransformDataProcess):
    def recv_packet(self, packet, stream_route, stream_id):
        log.debug("received granule: %r from stream %r", packet, stream_id)
