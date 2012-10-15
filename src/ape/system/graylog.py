"""
create and manage rabbit clusters
"""

from ape.system.system_configuration import MANUAL_RESOURCE_TYPE, LAUNCH_CREATED_RESOURCE_TYPE, SCALABLE_RESOURCE_TYPE
from ape.system.resource_cluster import ManualCluster
from ape.common.types import ApeException

KEY_PREFIX = 'graylog'
TYPE_KEY='graylog.type'

def launch_graylog(config):
    type = config.get(TYPE_KEY)
    if not type:
        return None
    if type==MANUAL_RESOURCE_TYPE:
        return ManualGraylogCluster(config)
#    elif type==LAUNCH_CREATED_RESOURCE_TYPE:
#        return LaunchCreatedCouch(config)
#    elif type==SCALABLE_RESOURCE_TYPE:
#        cluster = ScalableCouchCluster(config)
#        cluster.start_launch()
#        return cluster
    else:
        raise ApeException('NOT YET SUPPORTED: graylog type %s' % type)

def reconnect_graylog(config):
    type = config.get(TYPE_KEY)
    if not type:
        return None
    if type==MANUAL_RESOURCE_TYPE:
        return launch_graylog(config)
    else:
        raise ApeException('NOT YET SUPPORTED: graylog type %s' % type)

class ManualGraylogCluster(ManualCluster):
    def __init__(self, config):
        super(ManualGraylogCluster,self).__init__(config,KEY_PREFIX)
    def get_elasticsearch(self):
        pass