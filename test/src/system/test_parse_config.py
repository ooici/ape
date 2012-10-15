
import unittest
from ape.system.system_configuration import Configuration
from ape.system.couch import launch_couch
from ape.system.rabbit import launch_rabbit
from ape.system.elasticsearch import launch_elasticsearch
from ape.system.graylog import launch_graylog

class TestParseManual(unittest.TestCase):
    def test_read_file(self):
        config = Configuration('test/src/system/system-manual.yml')
        couch = launch_couch(config)
        self.assertEquals(couch.get_hostname(), 'couch-hostname')

        rabbit = launch_rabbit(config)
        es = launch_elasticsearch(config)
        graylog = launch_graylog(config)
        graylog_es = graylog.get_elasticsearch()


if __name__ == '__main__':
    unittest.main()