"""
parse system description YAML file
"""

import yaml

#### rabbit, couch, elasticsearch will be one of these types
#
# the ape test creates its own and can programmatically control them
SCALABLE_RESOURCE_TYPE='scale'
# the resource already exists somewhere and ape just uses it
MANUAL_RESOURCE_TYPE='manual'
# the CEI launch plan will create this resource and containers will already be configured to use it
LAUNCH_CREATED_RESOURCE_TYPE='launch-generated'

class Configuration(object):
    def __init__(self, desc):
        if isinstance(desc, str):
            self.config = self._read_file(desc)
        elif isinstance(desc, dict):
            self.config = desc
        else:
            raise ApeException('configuration must be defined with a YAML filename or dictionary')

    def _read_file(self, name):
        with open(name, 'r') as f:
            return yaml.load(f)

    def get(self, key):
        """
        return entries in a dictionary/list structure from a YAML file.
        uses keys of the form 'a.b.3.c' to represent self.config['a']['b'][3]['c']
        where each dot-separated token is either a dictionary key or list index.
        raises exception if index out of bounds, but returns null if dictionary key not found.
        """
        keys = key.split('.')
        branch = self.config
        for item in keys:
            if isinstance(branch,dict):
                if item in branch:
                    value = branch[item]
                else:
                    return None
            elif isinstance(branch,list):
                index = int(item)
                value = branch[index]
            else:
                raise Exception('reached %s leaf before expected: %s' % (branch.__class__.__name__, key))
            # if there are more keys, they descend from here
            branch = value

        # otherwise this is the final target, but wrap in new Configuration object
        if isinstance(value, list):
            return [ Configuration(item) if isinstance(item, dict) else item for item in value ]
        elif isinstance(value, dict):
            return Configuration(value)
        else:
            return value

    def as_dict(self):
        return self.config

    def iteritems(self):
        return self.config.iteritems()