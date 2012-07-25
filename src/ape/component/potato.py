"""
component to put load on the couch db from within the container

this component makes direct DB calls instead of using the pycc couchdb interface
"""
import random
import string
from threading import Thread
import time
import traceback
from pyon.util.log import log
from pyon.core.bootstrap import CFG
from ape.common.requests import StartRequest, StopRequest, ChangeConfiguration, PerformanceResult
from ape.common.types import ApeComponent, ApeException, ApeRequest
import couchdb
from pyon.datastore.id_factory import SaltedTimeIDFactory, RandomIDFactory

class Configuration(object):
    database = 'testchip'
    sleep_between_operations = 0
    sleep_between_cycles = 0
    sleep_between_reports = 30
    # operations per cycle
    read_count = 85
    create_count = 10
    update_count = 5
    delete_count = 0
    # document
    id_salt = ['a','b','c'] #None # None=UUIDs for keys; otherwise should be unique per host
    key_count = 10
    key_length = 10
    value_length = 10
    update_keys = 3

class ReadAllDocs(ApeRequest): pass
class PerformOneCycle(ApeRequest): pass

class Potato(ApeComponent):
    def _start(self):
        self.reporter = _ReportingThread(self.configuration, self)
        self.reporter.start()
        self.thread = _OperationThread(self.configuration, self.agent.container,self.reporter)
        self.thread.start()

    def _stop(self):
        self.reporter.shutdown()
        self.thread.shutdown()
        self.thread = None

    def perform_action(self, request):
        if isinstance(request, StartRequest):
            self.reporter.set_enabled(True)
            self.thread.set_enabled(True)
        elif isinstance(request, StopRequest):
            self.reporter.set_enabled(False)
            self.thread.set_enabled(False)
        elif isinstance(request, ChangeConfiguration):
            self.thread.set_config(request.configuration)
        elif isinstance(request, ReadAllDocs):
            self.thread.read_all_docs(True)
        elif isinstance(request, PerformOneCycle):
            self.thread.perform_iteration()
            self.reporter.report_status()
        else:
            raise ApeException('couch potato does not know how to: ' + str(request))
        
    def get_report(self):
        return self.thread.get_report()

CHARS=string.ascii_uppercase + string.digits
def random_string(length):
    return ''.join(random.choice(CHARS) for x in range(length))

class _OperationThread(Thread):
    def __init__(self,config, container, reporter):
        super(_OperationThread,self).__init__()
        self.config = config
        self.container = container
        self.enabled = False
        self.shutdown = False
        self.documents = []
        self.reporter = reporter
        host = CFG.server.couchdb.host
        port = CFG.server.couchdb.port
        username = CFG.server.couchdb.username
        password = CFG.server.couchdb.password
        if username:
            url = "http://%s:%s@%s:%s" % (username,password,host,port)
        else:
            url = "http://%s:%s" % (host,port)
        self.server = couchdb.Server(url)
        if self.config.database in self.server:
            self.db = self.server[self.config.database]
        else:
            self.db = self.server.create(self.config.database)
        if config.id_salt is None:
            self.ids = RandomIDFactory()
        else:
            self.ids = SaltedTimeIDFactory()
            self.ids._salt = config.id_salt
        self.reset_metrics()

    def set_config(self, config):
        self.config = config
        self.db = self.server[config.database]
    def set_enabled(self, is_enabled):
        if is_enabled:
            self.reset_metrics()
            self.read_all_docs()
            self.reporter.report_status()
            self.reset_metrics()
        self.enabled = is_enabled
    def shutdown(self):
        self.shutdown = True
        self.db = None # cause operations to throw exception, exit cycle faster

    def read_all_docs(self):
        rows = self.db.view("_all_docs", include_docs=False)
        self.documents = [ row.id for row in rows ]

    def read_doc(self):
        id = random.choice(self.documents)
        return self.db.get(id)
    def create_doc(self):
        doc = { '_id': self.ids.create_id() }
        for n in xrange(self.config.key_count):
            key = random_string(self.config.key_length)
            doc[key] = random_string(self.config.value_length)
        self.db.save(doc)
    def update_doc(self):
        doc = self.read_doc()
        for n in xrange(self.config.update_keys):
            key = None
            while not key or key=='_id' or key=='_rev':
                key = random.choice(doc.keys())
            doc[key] = random_string(self.config.value_length)
        self.db.save(doc)
    def delete_doc(self):
        doc = self.read_doc()
        self.db.delete(doc)

    def run(self):
        while not self.shutdown:
            if self.enabled:
                self.perform_iteration()
                time.sleep(self.config.sleep_between_cycles)
            else:
                time.sleep(max(1,self.config.sleep_between_cycles))

    def perform_iteration(self):
        """perform configured number of each operation in random order"""
        sequence = ['R']*self.config.read_count + ['C']*self.config.create_count + ['U']*self.config.update_count + ['D']*self.config.delete_count
        random.shuffle(sequence)
        for c in sequence:
            try:
                if c[0]=='C':
                    self.create_doc()
                    self.create_operations+=1
                elif c[0]=='R':
                    self.read_doc()
                    self.read_operations+=1
                elif c[0]=='U':
                    self.update_doc()
                    self.update_operations+=1
                elif c[0]=='D':
                    self.delete_doc()
                    self.delete_operations+=1
                else:
                    raise ApeException('this should never happen: ' + repr(c))
            except Exception:
                if self.shutdown:
                    return
                log.info('%s operation failed: %s' % (c[0], traceback.format_exc()))
            time.sleep(self.config.sleep_between_operations)

    def reset_metrics(self):
        self.start_time = time.time()
        self.create_operations = 0
        self.read_operations = 0
        self.update_operations = 0
        self.delete_operations = 0

    def get_report(self):
        elapsed = time.time() - self.start_time
        return { 'elapsed': elapsed,
                 'create': self.create_operations,
                 'read': self.read_operations,
                 'update': self.update_operations,
                 'delete': self.delete_operations }

class _ReportingThread(Thread):
    def __init__(self, config, component):
        super(_ReportingThread,self).__init__()
        self.config = config
        self.component = component
        self.shutdown = False
        self.enabled = False

    def set_enabled(self, is_enabled):
        self.enabled = is_enabled
    def shutdown(self):
        self.shutdown = True

    def run(self):
        while not self.shutdown:
            if self.enabled:
                time.sleep(self.config.sleep_between_reports)
                self.report_status()
            else:
                time.sleep(max(1,self.config.sleep_between_reports))

    def report_status(self):
        report = self.component.get_report()
        message = PerformanceResult(report)
        self.component.report(message)
