''' simulated instrument types '''
from ape.common.types import ApeException

from prototype.sci_data.constructor_apis import StreamDefinitionConstructor, PointSupplementConstructor
from interface.objects import Taxonomy
from pyon.ion.granule.record_dictionary import RecordDictionaryTool
from pyon.ion.granule.taxonomy import TaxyTool
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
    # TODO: use_new_granule as configuration option
    def __init__(self):
        sdc = StreamDefinitionConstructor(description='Parsed conductivity temperature and pressure observations from a Seabird 37 CTD', nil_value=-999.99, encoding='hdf5')
        sdc.define_temporal_coordinates(reference_frame='http://www.opengis.net/def/trs/OGC/0/GPS', definition='http://www.opengis.net/def/property/OGC/0/SamplingTime',
            reference_time='1970-01-01T00:00:00Z', unit_code='s' )
        sdc.define_geospatial_coordinates(definition="http://www.opengis.net/def/property/OGC/0/PlatformLocation",reference_frame='urn:ogc:def:crs:EPSG::4979')

        # TODO: remove unit, range, definition
        # used only in old-style granule
        sdc.define_coverage(field_name='value',
                            field_definition="urn:x-ogc:def:phenomenon:OGC:temperature",
                            field_units_code='Cel',
                            field_range=[-99999.0, 99999.0])
        self.stream_definition = sdc.close_structure()

        # used only in new-style granule
        self.tax = TaxyTool()
        self.tax.add_taxonomy_set('value')
        self.tax.add_taxonomy_set('latitude')
        self.tax.add_taxonomy_set('longitude')
        self.use_new_granule = True
        self.message_size = 1
        self.position = (0,0,0)

    def get_granule(self, **args):
        if self.use_new_granule:
            return self.get_granule_NEW(**args)
        else:
            return self.get_granule_OLD(**args)

    def get_granule_OLD(self, stream_id=None, time=None, **_):
        psc = PointSupplementConstructor(point_definition=self.stream_definition, stream_id=stream_id)
        point = psc.add_point(time=time, location=self.get_location(time))
        psc.add_scalar_point_coverage(point_id=point, coverage_id='value', value=self.get_value(time))
        granule = psc.close_stream_granule()
        return granule

    def get_granule_NEW(self, producer_id='UNUSED', time=None, **_):
        payload = RecordDictionaryTool(self.tax)
        lat,lon,_ = self.get_location(time)
        value = self.get_value(time)
        payload['value'] = array([value]*self.message_size)
        payload['latitude'] = array([lat]*self.message_size)
        payload['longitude'] = array([lon]*self.message_size)
#        log.debug('sending granule: ' + repr(payload))
        granule = build_granule(data_producer_id=producer_id, taxonomy=self.tax, record_dictionary=payload)
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