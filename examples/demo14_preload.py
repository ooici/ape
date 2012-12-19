"""
test the ape preload component

can access IONLoader from ape test to read normal google doc/CSV files
or define iterative preload templates
"""

import time
import logging
import gevent.monkey
gevent.monkey.patch_all(aggressive=False)
from ape.manager.simple_manager import SimpleManager, Listener
from ape.component.preloader import Preloader, PerformPreload, NotifyPreloadComplete, PathConfiguration, TemplateConfiguration
from ape.common.requests import PingRequest, AddComponent
from ape.common.messages import  component_id
from ion.processes.bootstrap.ion_loader import TESTED_DOC

log = logging.getLogger('demo14')

def _step(msg):
    log.info('*** ' + msg)

class PreloadListener(Listener):
    results = {}
    def on_message(self, message):
        if isinstance(message.result, NotifyPreloadComplete):
            self.results[message.result.id] = message.result

    def clear_result(self, id):
        del self.results[id]
    def wait_for_result(self, id):
        while id not in self.results:
            time.sleep(2)
        return self.results[id]

def main():
    m = SimpleManager()
    l = PreloadListener()
    m.add_listener(l)
    _step('have manger')

    # first preload a scenario from the normal google doc
    #
    doc = PathConfiguration(path=TESTED_DOC, scenarios=["BASE"])
    req = PerformPreload("goog", doc)
    m.send_request(AddComponent(Preloader('loader', None, None)), component_filter=component_id('AGENT'))
    m.send_request(req, component_filter=component_id('loader'))
    _step('started doc preload')

    result = l.wait_for_result('goog')
    _step('preload finished.  success? %r' % result.success)

    # now use a preload template:
    # create 10 users where each field is either a value string
    # or a template expression with %d substituted with values from 1 to 10
    #
    rows = { 'row_type': 'User',
        'ID': 'TEMPLATE_USER_%d',
        'subject': 'TBD',
        'name': 'Full Name %d',
        'description': 'Very %d descriptive',
        'contact_id': '',
        'role_ids': ''
    }
    template = TemplateConfiguration(range=xrange(1,10), templates=[rows])
    req = PerformPreload("rowz", template)
    m.send_request(req, component_filter=component_id('loader'))
    _step('started template preload')

    result = l.wait_for_result('rowz')
    _step('preload finished.  success? %r' % result.success)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
