''' simulated instrument types '''
from ape.common.types import ApeException

from prototype.sci_data.constructor_apis import StreamDefinitionConstructor, PointSupplementConstructor
from pyon.ion.granule.granule import build_granule, Granule
from interface.objects import Taxonomy
from pyon.ion.granule.record_dictionary import RecordDictionaryTool
from pyon.ion.granule.taxonomy import TaxyTool
from numpy import array
from pyon.public import log

def build_instrument(configuration):
    ''' factory method to build instruments based on configuration '''
    if configuration is None:
        return Simple3DInstrument()
    if callable(configuration):
        i = Simple3DInstrument()
        i.get_value = configuration
        return i
    if isinstance(configuration, int):
        i = Simple3DInstrument()
        i.message_size = configuration
        return i
    raise ApeException("don't know how to build instrument from " + repr(configuration))

class InstrumentType(object):
    ''' base type to define a simulated instrument '''
    model_name = 'Simulated Instrument'
    stream_name = None
    stream_definition = None

    def get_granule(self, stream_id=None, time=None):
        pass

class Simple3DInstrument(InstrumentType):
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
        self.use_new_granule = True

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
        payload = RecordDictionaryTool(self.tax, length=self.message_size)
        value = self.get_value(time)
        payload['value'] = array([value]*self.message_size)
        granule = build_granule(data_producer_id=producer_id, taxonomy=self.tax, record_dictionary=payload)
        return granule

    def get_location(self, time):
        return (0,0,0)#(longitude, latitude, elevation)
    def get_value(self, time):
        return 0.1