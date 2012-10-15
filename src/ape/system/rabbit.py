"""
create and manage rabbit clusters
"""

from ape.system.system_configuration import MANUAL_RESOURCE_TYPE, LAUNCH_CREATED_RESOURCE_TYPE, SCALABLE_RESOURCE_TYPE
from ape.system.resource_cluster import ManualCluster
from ape.common.types import ApeException
import os

KEY_PREFIX = 'rabbit'
TYPE_KEY='rabbit.type'

def launch_rabbit(config):
    type = config.get(TYPE_KEY)
    if type==MANUAL_RESOURCE_TYPE:
        return ManualRabbitCluster(config)
#    elif type==LAUNCH_CREATED_RESOURCE_TYPE:
#        return LaunchCreatedCouch(config)
#    elif type==SCALABLE_RESOURCE_TYPE:
#        cluster = ScalableCouchCluster(config)
#        cluster.start_launch()
#        return cluster
    else:
        raise ApeException('NOT YET SUPPORTED: rabbit type %s' % type)

def reconnect_rabbit(config):
    type = config.get(TYPE_KEY)
    if type==MANUAL_RESOURCE_TYPE:
        return launch_rabbit(config)
    else:
        raise ApeException('NOT YET SUPPORTED: rabbit type %s' % type)

class ManualRabbitCluster(ManualCluster):
    def __init__(self, config):
        super(ManualRabbitCluster,self).__init__(config,KEY_PREFIX)
        os.environ['RABBITMQ_HOST'] = self.get_hostname()
        os.environ['RABBITMQ_USERNAME'] = self.get_username()
        os.environ['RABBITMQ_PASSWORD'] = self.get_password()

