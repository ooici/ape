"""
component to put load on rabbit MQ from within the container

"""
from gevent.event import AsyncResult
from pika.adapters.select_connection import SelectConnection
from pika.connection import ConnectionParameters
from pika.credentials import PlainCredentials
from pika.reconnection_strategies import SimpleReconnectionStrategy
from pyon.util.log import log
from pyon.core.bootstrap import CFG
from ape.common.types import ApeComponent, ApeException, ApeRequest, ApeResult
import couchdb
from pyon.datastore.id_factory import SaltedTimeIDFactory, RandomIDFactory
from ion.processes.bootstrap.ion_loader import IONLoader, DEFAULT_CATEGORIES
from ion.processes.bootstrap.ui_loader import UILoader

class PerformPreload(ApeRequest):
    def __init__(self, id, config):
        self.id = id
        self.config = config

class NotifyPreloadComplete(ApeResult):
    def __init__(self, id, success=True, message=None):
        self.id = id
        self.success = success
        self.message = message

class Configuration(object):
    pass

class PathConfiguration(Configuration):
    def __init__(self, path=None, scenarios=None, resources=None, uipath=None):
        self.path = path
        self.scenarios = scenarios
        self.resources = resources
        self.uipath = uipath

class TemplateConfiguration(Configuration):
    def __init__(self, range, templates):
        self.range = range
        self.templates = templates

class Preloader(ApeComponent):
    def perform_action(self, request):
        if not isinstance(request, PerformPreload):
            raise ApeException('message producer does not know how to: ' + str(request))
        if isinstance(request.config, PathConfiguration):
            task = _PreloadPathTask(request.config, self.agent, self.agent.container)
        else:
            task = _PreloadTemplateTask(request.config, self.agent, self.agent.container)

        task.run()
        result = NotifyPreloadComplete(request.id, success=task.success)
        self.report(result)

class _PreloadBaseTask(object):
    loader = IONLoader()
    def __init__(self, config, process, container):
        self.config = config
#        self.loader = IONLoader()
        self.loader.categories = DEFAULT_CATEGORIES
        self.loader.debug = self.loader.loadooi = self.loader.loadui = \
          self.loader.exportui = self.loader.update = self.loader.bulk = False
        self.loader.container = container
        self.loader.rpc_sender = process
        self.loader.CFG = process.CFG

#        self.loader.obj_classes = {}     # Cache of class for object types
#        self.loader.resource_ids = {}    # Holds a mapping of preload IDs to internal resource ids
#        self.loader.resource_objs = {}   # Holds a mapping of preload IDs to the actual resource objects
#        self.loader.existing_resources = None
#        self.loader.unknown_fields = {} # track unknown fields so we only warn once
#        self.loader.constraint_defs = {} # alias -> value for refs, since not stored in DB
#        self.loader.contact_defs = {} # alias -> value for refs, since not stored in DB
#        self.loader.stream_config = {} # name -> obj for StreamConfiguration objects, used by *AgentInstance

        self.success = False

    def run(self):
        try:
            self.prepare_loader()
        except:
            log.error('preload component failed to initialize', exc_info=True)
            return
        try:
            self.perform_preload()
            self.success = True
        except:
            log.error('preload component failed to load rows', exc_info=True)
            return

    def prepare_loader(self):
        if not self.loader.resource_ids:
            self.loader._load_system_ids()
        self.loader._prepare_incremental()

class _PreloadPathTask(_PreloadBaseTask):
    def perform_preload(self):
        self.loader.path = self.config.path
        self.loader.categories = self.config.resources
        self.loader.attachment_path="res/preload/r2_ioc/attachments"

        if self.config.uipath:
            ui_loader = UILoader(self.loader)
            ui_loader.load_ui(self.config.uipath)

        self.loader.load_ion(self.config.scenarios)

class _PreloadTemplateTask(_PreloadBaseTask):
    def perform_preload(self):
        log.info('config: %r', self.config)
        row = {}
        self.loader.attachment_path="res/preload/r2_ioc/attachments",
        self.loader.prepare_loader()
        for type in DEFAULT_CATEGORIES:
            log.info('checking for template of category %s', type)
            for template in self.config.templates:
                log.debug('template %r', template)
                if template['row_type']==type:
                    log.info('loading category %s from template', type)
#                    spec = self.config.rowspec[type]
                    for index in self.config.range:
                        row.clear()
                        for key,field_template in template.iteritems():
                            if key=='row_type':
                                continue
                            field_template = str(field_template) if field_template else ""
                            if '%' in field_template:
                                # substitute index for each %d in field_template
                                value = field_template % tuple([ index for n in xrange(field_template.count('%')) ])
                            else:
                                value = field_template
                            row[key] = value
                        self.loader.load_row(type, row)
