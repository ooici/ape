"""
create and manage bigcouch clusters
"""

from ape.system.system_configuration import MANUAL_RESOURCE_TYPE, LAUNCH_CREATED_RESOURCE_TYPE, SCALABLE_RESOURCE_TYPE
from ape.system.resource_cluster import ManualCluster
from ape.common.types import ApeException
import os

KEY_PREFIX = 'couch'
TYPE_KEY='couch.type'

def launch_couch(config):
    type = config.get(TYPE_KEY)
    if type==MANUAL_RESOURCE_TYPE:
        return ManualCouchCluster(config)
#    elif type==LAUNCH_CREATED_RESOURCE_TYPE:
#        return LaunchCreatedCouch(config)
#    elif type==SCALABLE_RESOURCE_TYPE:
#        cluster = ScalableCouchCluster(config)
#        cluster.start_launch()
#        return cluster
    else:
        raise ApeException('NOT YET SUPPORTED: couch type ' + type)

def reconnect_couch(config):
    type = config.get(TYPE_KEY)
    if type==MANUAL_RESOURCE_TYPE:
        return launch_couch(config)
    else:
        raise ApeException('NOT YET SUPPORTED: couch type ' + type)

class ManualCouchCluster(ManualCluster):
    def __init__(self, config):
        super(ManualCouchCluster,self).__init__(config, KEY_PREFIX)
        os.environ['COUCHDB_HOST'] = self.get_hostname()
        os.environ['COUCHDB_USERNAME'] = self.get_username()
        os.environ['COUCHDB_PASSWORD'] = self.get_password()
