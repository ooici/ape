''' simulated instrument types '''
from ape.common.types import ApeException

from prototype.sci_data.constructor_apis import StreamDefinitionConstructor, PointSupplementConstructor
from interface.objects import Taxonomy
from ion.services.dm.utility.granule import RecordDictionaryTool
from numpy import array
from pyon.public import log
from math import sin

def build_instrument(configuration):
    ''' factory method to build instruments based on configuration '''
    if configuration is None:
        return SimpleInstrument()
    if callable(configuration):
        i = SimpleInstrument()
        i.get_value = configuration
        return i
    if isinstance(configuration, int):
        i = SimpleInstrument()
        i.message_size = configuration
        return i
    if isinstance(configuration, tuple):
        return OscillatingInstrument(configuration)
    raise ApeException("don't know how to build instrument from " + repr(configuration))

class InstrumentType(object):
    ''' base type to define a simulated instrument '''
    model_name = 'Simulated Instrument'
    stream_name = None
    stream_definition = None

    def get_granule(self, stream_id=None, time=None):
        pass

class SimpleInstrument(InstrumentType):
    ''' instrument generating a single value at each time t with a fixed (x,y,h) location '''
    def __init__(self):
        #self.parameter_dictionary = DatasetManagementServiceClient(node=self.agent.container.node).read_parameter_dictionary_by_name('ctd_parsed_param_dict')
        #self.parameter_dictionary = get_param_dict('ctd_parsed_param_dict')
        self.message_size = 1
        self.position = (0,0,0)

    def get_granule(self, time=None, pd=None):
        lat,lon,_ = self.get_location(time)
        value = self.get_value(time)

        pkg = RecordDictionaryTool(pd)
        pkg['salinity'] = array([value]*self.message_size)
        pkg['lat'] = array([lat]*self.message_size)
        pkg['lon'] = array([lon]*self.message_size)
        granule = pkg.to_granule()
        return granule

    def get_location(self, time):
        return self.position  #(longitude, latitude, elevation)
    def get_value(self, time):
        return 0.1

class OscillatingInstrument(SimpleInstrument):
    def __init__(self, tuple):
        super(OscillatingInstrument, self).__init__()
        x, y, self.phase, self.frequency, self.freq2 = tuple
        self.position = (y, x, 0)
    def get_value(self, time):
        freq_offset = self.freq2*sin(time*self.freq2)
        freq = self.frequency + freq_offset
        return sin(time*freq+self.phase)