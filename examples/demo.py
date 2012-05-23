import gevent.monkey
from ape.component.transform import TransformComponent
from ape.component.transform import Configuration as TransformConfiguration

gevent.monkey.patch_all(aggressive=False)

from ape.manager.simple_manager import SimpleManager, InventoryListener, Listener
from ape.common.requests import PingRequest, AddComponent, StartRequest, InventoryRequest, StopRequest, PerformanceResult
from ape.component.instrument_simulator import InstrumentSimulator
from ape.component.instrument_simulator import Configuration as InstrumentConfiguration
from ape.component.consumer import DataProductConsumer
from ape.component.consumer import Configuration as ConsumerConfiguration
from ape.common.messages import  component_id, agent_id, component_type
from time import sleep
import math
from numpy import array, zeros

def wait(a):
    raw_input('--- press enter to continue ---')
#    sleep(a)


ARRAY_SIZE = 10


create_array = '''
from numpy import zeros
ARRAY_SIZE = ''' + str(ARRAY_SIZE) + '''
if not hasattr(self, 'gridvalue'):
    self.gridvalue = zeros((ARRAY_SIZE,ARRAY_SIZE))
x = int(input['longitude'][0])
y = int(input['latitude'][0])
#print 'want to set gridvalue[%d,%d]='%(x,y) + repr(input['value'][0])
self.gridvalue[x,y] = input['value'][0]
if x==0 and y==0:
    output['value'] = self.gridvalue
else:
    output = None
'''

create_image = '''
from demo import save_plot
save_plot(input)
output = None
'''

def save_plot(input):
    print 'starting create_image'
    from mpl_toolkits.mplot3d import axes3d
    import matplotlib.pyplot as plt
    import numpy as np
#    from pylab import *
    print 'create_image: imported'

    fig = plt.figure()
    ax = fig.gca(projection='3d')
    X, Y = np.mgrid[0:ARRAY_SIZE, 0:ARRAY_SIZE]
#    Z = np.maximum(0.5, np.cos(X) + np.cos(Y))
#    print 'orig type: ' + Z.__class__.__name__
#    print repr(Z)
    Z = input['value']
#    print 'new type: ' + Z.__class__.__name__
#    print repr(Z)
    print 'create_image: created values'

    surf = ax.plot_surface(X, Y, Z, cmap='autumn', cstride=1, rstride=1)
    ax.set_xlabel("X-Label")
    ax.set_ylabel("Y-Label")
    ax.set_zlabel("Z-Label")
    ax.set_zlim(-2, 3)
    print 'create_image: plot'
    try:
        ## HACK HACK HACK -- need to use a true service and plumb into the UI
        plt.savefig('/Users/jnewbrough/Dev/code/ape/tmp/image.png')
        print 'create_image: saved'
    except Exception as ex:
        print 'exception: ' + str(ex)

def try_it():
    a = zeros((2,2))
    print a.__class__.__name__
    input = { 'value': a }
    save_plot(input)

def main():
    l1 = InventoryListener()
    m = SimpleManager()
    m.add_listener(l1)

    # get inventory -- see what agents we have running
    m.send_request(InventoryRequest())
    sleep(5)

    agent = l1.inventory.keys()[0]
    print 'using agent: ' + agent


    print 'adding %d producers'%(ARRAY_SIZE*ARRAY_SIZE)
    transform_config = TransformConfiguration(transform_function=create_array) #(lambda input: dict(value=sum(input['value']))))
    for x in xrange(ARRAY_SIZE):
        for y in xrange(ARRAY_SIZE):
            suffix = '%d-%d'%(x,y)
            raw_dataproduct = 'raw-'+suffix
            instrument_magic = (x, y, (x*x+20*math.sin(y/5))/50, .1, math.sin(y/3)/0.001)
            producer_config = InstrumentConfiguration(raw_dataproduct, 2, instrument_configuration=instrument_magic,
                persist_product=False, report_timing=False)
            producer = InstrumentSimulator('producer-'+suffix, None, producer_config)
            m.send_request(AddComponent(producer), agent_filter=agent_id(agent), component_filter=component_id('AGENT'))

            transform_config.add_input(raw_dataproduct)

    print 'adding transform'
    transform_config.add_output('gridvalues')
    transform_config.add_output_field('value')
    transform = TransformComponent('transform', None, transform_config)
    m.send_request(AddComponent(transform), agent_filter=agent_id(agent), component_filter=component_id('AGENT'))

    print 'adding second transform'
    transform2_config = TransformConfiguration(transform_function=create_image)
    transform2_config.add_input('gridvalues')
    transform2_config.add_output('image')
    transform2_config.add_output_field('value')
    transform2 = TransformComponent('image', None, transform2_config)
    m.send_request(AddComponent(transform2), agent_filter=agent_id(agent), component_filter=component_id('AGENT'))

    print 'adding consumer'
    consumer = DataProductConsumer('consumer', None, ConsumerConfiguration('gridvalues', log_value=True))
    m.send_request(AddComponent(consumer), agent_filter=agent_id(agent), component_filter=component_id('AGENT'))

    print 'starting data flow'
    m.send_request(StartRequest(), agent_filter=agent_id(agent), component_filter=component_type(InstrumentSimulator))
    m.send_request(StartRequest(), agent_filter=agent_id(agent), component_filter=component_id('transform'))
    m.send_request(StartRequest(), agent_filter=agent_id(agent), component_filter=component_id('image'))
    m.send_request(StartRequest(), agent_filter=agent_id(agent), component_filter=component_id('consumer'))

    # log results as they arrive
    wait(30)
    m.send_request(StopRequest(), component_filter=component_type(InstrumentSimulator))
    print 'data producer stopped'
    sleep(5)
#    wait(2)

if __name__ == "__main__":
    main()
