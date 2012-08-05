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
    threads = 4
    # operations per cycle
    read_count = 85
    create_count = 10
    update_count = 5
    delete_count = 0
    bulk_frequency = 0
    bulk_count = 10
    # document
    id_salt = ['a','b','c'] #None # None=UUIDs for keys; otherwise should be unique per host
    key_count = 10
    key_length = 10
    value_length = 10
    update_keys = 3

class ReadAllDocs(ApeRequest): pass
class PerformOneIteration(ApeRequest): pass

class Potato(ApeComponent):
    def _start(self):
        self.threads_enabled = False
        self.threads_shutdown = False
        self.reporter = _ReportingThread(self)
        self.reporter.start()
        self.threads = []
        if self.configuration.id_salt is None:
            ids = RandomIDFactory()
        else:
            ids = SaltedTimeIDFactory()
            ids._salt = self.configuration.id_salt

        log.debug('starting %d threads', self.configuration.threads)
        for x in xrange(self.configuration.threads):
            thread = _OperationThread(self, ids)
            thread.start()
            self.threads.append(thread)
        self.documents = []

    def _stop(self):
        self.threads_enabled = False
        self.threads_shutdown = True

    def perform_action(self, request):
        if isinstance(request, StartRequest):
            self.reconfigure()
            self.reset_metrics()
            self.threads_enabled = True
        elif isinstance(request, StopRequest):
            self.threads_enabled = False
            for t in self.threads:
                t.db = None
        elif isinstance(request, ChangeConfiguration):
            self.configuration = request.configuration
            self.reconfigure()
        elif isinstance(request, ReadAllDocs):
            self.read_all_docs()
        elif isinstance(request, PerformOneIteration):
            self.reset_metrics()
            self.threads[0].perform_iteration()
            self.reporter.report_status()
        else:
            raise ApeException('couch potato does not know how to: ' + str(request))

    def read_all_docs(self):
        self.documents = self.threads[0].read_all_docs()
    def reconfigure(self):
        for t in self.threads:
            t.set_config(self.configuration)
        self.read_all_docs()
    def reset_metrics(self):
        for t in self.threads:
            t.reset_metrics()
    def get_report(self):
        out = {'create':0, 'read':0, 'update':0, 'delete':0 }
        sum_elapsed = count = 0
        for t in self.threads:
            report = t.get_report()
            sum_elapsed += report['elapsed']
            count+=1
            for key in 'create', 'read', 'update', 'delete':
                out[key] += report[key]
        out['elapsed'] = sum_elapsed/count
        out['docs'] = len(self.documents)
        return out

CHARS=string.ascii_uppercase + string.digits
def random_string(length):
    return ''.join(random.choice(CHARS) for x in range(length))

class _OperationThread(Thread):
    def __init__(self, component, ids):
        super(_OperationThread,self).__init__()
        self.component = component
        self.config = component.configuration
        self.container = component.agent.container
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
        self.ids = ids
        self.reset_metrics()

    def set_config(self, config):
        self.config = config
        self.db = self.server[config.database]

    def read_all_docs(self):
        docs_each_pass=10001 # +1 b/c will have to skip first doc on all except first read
        documents = []
        not_first_pass = False
        more_to_read = True
        last_id = None
        while more_to_read:
            try:
                if not_first_pass:
                    # begin at last doc returned in last read
                    results = self.db.view("_all_docs", include_docs=False, limit=docs_each_pass, startkey_docid=last_id)
                    rows = results.rows
                else:
                    results = self.db.view("_all_docs", include_docs=False, limit=docs_each_pass-1)
                    rows = results.rows
            except:
                log.warn('exception reading all docs (done?)', exc_info=True)
                break
            if len(rows)<docs_each_pass:
                more_to_read = False

            if not_first_pass:
                rows = rows[1:]
            for row in rows:
                last_id = row.id
                documents.append(last_id)
            not_first_pass = True
        log.debug('read total %d ids', len(documents))
        return documents

    def read_doc(self):
        id = random.choice(self.component.documents)
        return self.db.get(id)

    def read_bulk(self):
        ids = [ random.choice(self.component.documents) for x in xrange(self.config.bulk_count) ]
        results = self.db.view("_all_docs", include_docs=True, keys=ids)
        docs = [ row.doc for row in results ]
        return docs

    def _make_doc(self):
        doc = { '_id': self.ids.create_id() }
        for n in xrange(self.config.key_count):
            key = random_string(self.config.key_length)
            doc[key] = random_string(self.config.value_length)
        return doc

    def create_doc(self):
        self.db.save(self._make_doc())

    def create_bulk(self):
        docs = [ self._make_doc() for x in xrange(self.config.bulk_count) ]
        self.db.update(docs)

    def _alter_doc(self, doc):
        for n in xrange(self.config.update_keys):
            key = None
            while not key or key=='_id' or key=='_rev':
                key = random.choice(doc.keys())
            doc[key] = random_string(self.config.value_length)

    def update_doc(self):
        doc = self.read_doc()
        self._alter_doc(doc)
        self.db.save(doc)

    def update_bulk(self):
        docs = self.read_bulk()
        for doc in docs:
            self._alter_doc(doc)
        self.db.update(docs)

    def delete_doc(self):
        doc = self.read_doc()
        self.db.delete(doc)

    def delete_bulk(self):
        docs = self.read_bulk()
        for doc in docs:
            doc['_deleted']=True
        self.db.update(docs)

    def run(self):
        while not self.component.threads_shutdown:
            if self.component.threads_enabled:
                self.perform_iteration()
                time.sleep(self.config.sleep_between_cycles)
            else:
                time.sleep(max(1,self.config.sleep_between_cycles))

    def perform_iteration(self):
        """perform configured number of each operation in random order"""
        log.debug('starting DB iteration')
        sequence = ['R']*self.config.read_count + ['C']*self.config.create_count + ['U']*self.config.update_count + ['D']*self.config.delete_count
        random.shuffle(sequence)
        for c in sequence:
            bulk = random.random()<self.config.bulk_frequency
            try:
                if bulk:
                    if c[0]=='C':
                        self.create_bulk()
                        self.create_operations+=self.config.bulk_count
                    elif c[0]=='R':
                        self.read_bulk()
                        self.read_operations+=self.config.bulk_count
                    elif c[0]=='U':
                        self.update_bulk()
                        self.update_operations+=self.config.bulk_count
                    elif c[0]=='D':
                        self.delete_bulk()
                        self.delete_operations+=self.config.bulk_count
                else:
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
                if self.component.threads_shutdown:
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
    def __init__(self, component):
        super(_ReportingThread,self).__init__()
        self.config = component.configuration
        self.component = component

    def run(self):
        while not self.component.threads_shutdown:
            if self.component.threads_enabled:
                time.sleep(self.config.sleep_between_reports)
                # check again in case was disabled while sleeping
                if self.component.threads_enabled:
                    self.report_status()
            else:
                time.sleep(max(1,self.config.sleep_between_reports))

    def report_status(self):
        report = self.component.get_report()
        message = PerformanceResult(report)
        self.component.report(message)
