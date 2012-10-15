"""
base classes for cluster resources like couch and rabbit
"""

HOSTNAME_KEY='.hostname'
USERNAME_KEY='.username'
PASSWORD_KEY='.password'

class BaseClusteredResource(object):
    # these three expected to raise exception if subclass has not set these values
    def get_hostname(self): return self.hostname
    def get_username(self): return self.username
    def get_password(self): return self.password

    # subclass should define way to tell if resource is ready to use
    def wait_for(self): pass

class ManualCluster(BaseClusteredResource):
    def __init__(self, config, prefix):
        self.hostname = config.get(prefix + HOSTNAME_KEY)
        self.username = config.get(prefix + USERNAME_KEY)
        self.password = config.get(prefix + PASSWORD_KEY)