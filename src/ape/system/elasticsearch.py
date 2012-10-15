"""
create and manage rabbit clusters
"""

from ape.system.system_configuration import MANUAL_RESOURCE_TYPE, LAUNCH_CREATED_RESOURCE_TYPE, SCALABLE_RESOURCE_TYPE
from ape.system.resource_cluster import ManualCluster
from ape.common.types import ApeException

KEY_PREFIX = 'elasticsearch'
TYPE_KEY='.type'

def launch_elasticsearch(config, prefix=KEY_PREFIX):
    if not config.get(prefix):
        return None

    type = config.get(prefix + TYPE_KEY)
    if type==MANUAL_RESOURCE_TYPE:
        return ManualElasticSearchCluster(config, prefix)
    #    elif type==LAUNCH_CREATED_RESOURCE_TYPE:
    #        return LaunchCreatedElasticSearch(config)
    #    elif type==SCALABLE_RESOURCE_TYPE:
    #        cluster = ScalableElasticSearchCluster(config)
    #        cluster.start_launch()
    #        return cluster
    else:
        raise ApeException('NOT YET SUPPORTED: elasticsearch type %s' % type)

def reconnect_elasticsearch(config, prefix=KEY_PREFIX):
    type = config.get(prefix + TYPE_KEY)
    if type==MANUAL_RESOURCE_TYPE:
        return launch_elasticsearch(config, prefix)
    else:
        raise ApeException('NOT YET SUPPORTED: elasticsearch type %s' % type)


class ManualElasticSearchCluster(ManualCluster):
    def __init__(self, config, prefix):
        super(ManualElasticSearchCluster,self).__init__(config,prefix)
