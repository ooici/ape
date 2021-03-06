""" manage the launch and shutdown of a collection of pycc containers with agents using cloudinitd

    uses troop configuration file such as my_test.trp:

    launch-name: test43    <-- name used by cloudinitd
    launch-target: ec2     <-- or local
    service-definitions: /some/sample/r2deploy.yml
    agent-service: agent_service_name  <-- which entry in r2deploy is ape agent, run on all pycc VMs
        config:
            typical: maybe   <-- added to agent definition in all generated deploy.yml (configure ape MQ?)

    containers:
        - name: container-with-services:
          count: 3
          services: *  <-- all services from r2deploy.yml
        - name: container-with-some-services:
          count: 2     <-- two identical servers launched
          services: 5  <-- with 5 services per server in order through file
        - name: container-basic-services:
          count: 2
          services: resource_registry_service, database_lookup_service
        - name: container-without-services:
          count: 5
          services:    <-- only agent
          config:
              special: of_course   <-- added to agent definition in generated deploy.yml

    NOTE: container-with-some-services actually defines multiple different kinds of nodes
        internally renamed to container-with-some-services-1, -2, etc

    NOTE: 'services: 1' as only node type should reproduce rel2levels.py behavior,
        one node launched per service listed

    when launched (from ape test script) we want to:
    - copy template launch-plan to working directory (local or remote)
    - create run levels in working directory
        (in above example, 3+2+5 run levels created PLUS 2x # services/5 for second entry)
    - modify launch plan conf files to list run levels created
    - run cloudinitd boot and wait until complete

    project setup:
        APE/resources/small-ec2.trp                  <-- sample troop definition used in example tests
        APE/launch-plan                              <-- copy of launch-plans/sandbox/lightweight or similar
        APE/launch-plan/templates
        APE/launch-plan/templates/pyon.conf          <-- template for config file for run level
        APE/launch-plan/templates/pyon.json          <-- template for service definition for run level
        APE/launch-plan/templates/troop-local.conf   <-- template for listing of run levels used by cloudinitd
        APE/launch-plan/templates/troop-ec2.conf     <-- template for listing of run levels used by cloudinitd
"""

from shutil import copytree, rmtree, copy

import yaml
import json
from string import Template
from ape.common.types import ApeException
from ape.manager.simple_manager import SimpleManager
from pyon.util.log import log
from math import log10
from os import mkdir, chdir, environ, listdir
from os.path import join, isdir, dirname, isabs
from cloudinitd.cli.boot import main as cloudinitd
from cloudinitd.user_api import CloudInitD
from cloudinitd.exceptions import APIUsageException, ConfigException

RESERVED_RUN_LEVELS=9  # container N is started as run level (N+RESERVED_RUN_LEVELS)

# TODO: generalize folder locations
WORK_DIRECTORY='tmp/launch-plan'
TEMPLATE_DIRECTORY='resources/launch-plan'
RUNLEVEL_CONFIG_TEMPLATE='templates/run-level.conf'
CONTAINER_CONFIG_TEMPLATE='templates/container-config.json'

class _NodeTypeDefinition(object):
    def __init__(self, name, services, count):
        self.name = name
        self.services = services
        self.count = int(count)
    def get_name(self):
        return self.name
    def get_services(self):
        return self.services
    def get_count(self):
        return self.count
    def set_count(self, count):
        self.count = count
    def __repr__(self):
        return self.__str__()
    def __str__(self):
        out = "%s (%d): " % (self.name, self.count)
        for service in self.services:
            out += "%s, " % service['name']
        return out

CREATED='unconfigured'
CONFIGURED='configured'
RUNNING='running'
FAILED='failed'

class Troop(object):
    def __init__(self, clobber=False, target=WORK_DIRECTORY, template=TEMPLATE_DIRECTORY, weather='sunny'):
        self.configuration = { }
        self.service_by_name = None
        self.clobber = clobber
        self.base_directory = self._get_base_directory()
        self.target_directory = target if isabs(target) else join(self.base_directory, target)
        self.template_directory = template if isabs(template) else join(self.base_directory, template)
        self.state = CREATED
        self.weather = weather

    def configure(self, config):
        """ use dictionary or yaml file for troop configuration """
        if self.state==RUNNING:
            raise ApeException('unable to reconfigure while troop state is ' + self.state)
        if isinstance(config, str):
            filename = config
            if not isabs(filename):
                filename = join(self.base_directory, config)
            with open(filename) as file:
                self.configuration = yaml.load(file)
            self.config_directory = dirname(filename)
        elif isinstance(config, dict):
            self.configuration = config
            self.config_directory = None
        else:
            raise ApeException('can not configure troop using a ' + config.__class__.__name__)

        self._add_node_types()
        launch_target = self.configuration['launch-target']
        self.launch_template_file = join(self.template_directory, 'templates', 'troop-on-' + launch_target + '.conf')
        self.launch_name = self.configuration['launch-name']
        self.state = CONFIGURED

    def set_name(self, name):
        if self.state==RUNNING or self.state==CREATED:
            raise ApeException('unable to reconfigure while troop state is ' + self.state)
        self.configuration['launch-name']=name

    def change_count(self, name, count):
        """ change count of container types with given name """
        if self.state==RUNNING or self.state==CREATED:
            raise ApeException('unable to reconfigure while troop state is ' + self.state)

        # find container description with matching name
        for node in self.configuration['containers']:
            changed_names = []
            if node['name']==name:
                # determine names of container types created from description
                if isinstance(node['services'], int):
                    index = 1
                    for start_index in xrange(0,len(self.services),node['services']):
                        indexed_name = '%s-%d' % (node['name'], index)
                        changed_names.append(indexed_name)
                        index += 1
                        print 'changing name %s' % indexed_name
                else:
                    changed_names.append(name)
                    print 'changing name %s' % name
                # then change counts
                for container in self.node_types:
                    if container.get_name() in changed_names:
                        container.set_count(count)
                return

        raise ApeException('unknown container description: ' + name)

    def _get_base_directory(self):
        if 'APE_HOME' in environ:
            return environ['APE_HOME']
        else:
            # WARNING: if package location of this file changes, this will fail!
            # assuming this source file is: APE_HOME/src/ape/manager/troop.py
            directory = dirname(dirname(dirname(dirname(__file__))))
            log.warn('APE_HOME is not set!  guessing location is: ' + directory)
            return directory

    def _add_node_types(self):
        self._read_services()

        self.node_types = []
        agent_services = [self.agent_service]
        for node in self.configuration['containers']:
            service_type = node['services']
            if service_type=='*':
                self.node_types.append(_NodeTypeDefinition(node['name'], self.services + agent_services, node['count']))
            elif isinstance(service_type, int):
                number_of_services = service_type
                index = 1
                for start_index in xrange(0,len(self.services),number_of_services):
                    end_index = min(start_index+number_of_services,len(self.services))
                    service_subset = self.services[start_index:end_index] + agent_services
                    name = "%s-%d" % (node['name'], index)
                    self.node_types.append(_NodeTypeDefinition(name, service_subset, node['count']))
                    index += 1
            elif isinstance(service_type, list):
                service_subset = []
                for service_name in service_type:
                    service_subset.append(self.service_by_name[service_name])
                service_subset += agent_services
                self.node_types.append(_NodeTypeDefinition(node['name'], service_subset, node['count']))
            elif service_type is None:
                service_subset = agent_services
                self.node_types.append(_NodeTypeDefinition(node['name'], service_subset, node['count']))
            else:
                raise ApeException('failed to parse node type %s: services: %s' % (node['name'], repr(service_type)))

    def _read_services(self):
        """ parse deploy.yml file for service definitions """
        if self.service_by_name is None:
            # read service definition file (deploy.yml)
            filename = self.configuration['service-definitions']
            if not isabs(filename):
                filename = join(self.config_directory, filename)
            with open(filename) as file:
                self._deploy_config = yaml.load(file)
            self.services = self._deploy_config['apps']

            # create name-->service mapping
            self.service_by_name = {}
            for service in self.services:
                name = service['name']
                if hasattr(self.service_by_name, name):
                    raise ApeException('deploy file %s has duplicate entry for service %s' % (filename, name))
                self.service_by_name[name] = service

            # remove agent service from default list of services (b/c already added to all containers)
            troop_agent_config = self.configuration['agent-service']
            agent_service_name = troop_agent_config['name']
            self.agent_service = self.service_by_name[agent_service_name]

            # combine agent service configuration with troop agent configuration
            if 'config' in troop_agent_config:
                if 'config' in self.agent_service:
                    self.agent_service['config'].update(troop_agent_config['config'])
                else:
                    self.agent_service['config'] = troop_agent_config['config']
            self.services.remove(self.agent_service)

    def get_container_count(self):
        """ determine how many pycc containers would be started based on the troop configuration """
        if self.state==CREATED:
            log.warn('container count called before troop was configured')
        total=0
        for node_type in self.node_types:
            total += node_type.get_count()
        return total

    def _runlevel_formatting_pattern(self):
        ''' format decimal run level with appropriate number of leading zeros to hold total number of run levels '''
        digits = len(str(self.get_container_count()+RESERVED_RUN_LEVELS-1))
        return '%0' + str(digits) + 'd'

    def create_launch_plan(self):
        """ create appropriate configuration files for cloudinitd launch of troop nodes """
#        self._check_environment()  #TODO
        self._copy_template()
        self._create_run_levels()

    def _copy_template(self):
        if isdir(self.target_directory):
            if self.clobber:
                rmtree(self.target_directory)
            else:
                raise ApeException('launch-plan folder already exists: %s' % self.target_directory)
        if not isdir(self.template_directory):
            raise ApeException('template launch-plan folder does not exist: %s' % self.template_directory)
        copytree(self.template_directory, self.target_directory)

    def _create_run_levels(self):
        self._read_services()
        with open(join(self.template_directory, CONTAINER_CONFIG_TEMPLATE)) as file:
            container_template = Template(file.read())
        with open(join(self.template_directory, RUNLEVEL_CONFIG_TEMPLATE)) as file:
            runlevel_template = Template(file.read())

        container_count=1
        run_level_descriptions = ''
        folder_pattern = 'pycc' + self._runlevel_formatting_pattern()
        level_pattern = 'level' + self._runlevel_formatting_pattern() + ': %s/run-level.conf\n'
        for node_type in self.node_types:
            for repeats in xrange(node_type.get_count()):
                log.debug("creating run level for container %d: node type %s" % (container_count, node_type.get_name()))
                folder_name = folder_pattern % container_count
                self._write_runlevel_configuration(folder_name, runlevel_template, node_type, container_template, container_count==1)
                run_level_descriptions += level_pattern % (container_count + RESERVED_RUN_LEVELS, folder_name)
                container_count += 1

        with open(join(self.template_directory, self.launch_template_file)) as file:
            launch_template = Template(file.read())
        launch_contents = launch_template.substitute(additional_runlevels=run_level_descriptions)
        with open(join(self.target_directory, 'troop-launch.conf'), 'w') as file:
            file.write(launch_contents)

    def _write_runlevel_configuration(self, folder_name, runlevel_template, node_type, container_template, bootstrap):
        # create run level folder
        folder = join(self.target_directory, folder_name)
        mkdir(folder)
        # create JSON description of services
        services_as_json = ''
        services_as_yaml = []
        for service in node_type.get_services():
            if services_as_json:
                services_as_json += ','
            services_as_json += json.dumps(service, indent=16)
            services_as_yaml.append(service)
        # substitute into templates and save files with appropriate names
        runlevel_configuration = runlevel_template.substitute(name=folder_name)
        with open(join(folder, 'run-level.conf'), 'w') as file:
            file.write(runlevel_configuration)
        container_configuration = container_template.substitute(runlevel=folder_name, name=node_type.get_name(), app_json=services_as_json)
        with open(join(folder, 'container-config.json'), 'w') as file:
            file.write(container_configuration)
        # write traditional deploy.yml
        data = dict(self._deploy_config)
        data['apps'] = services_as_yaml
        with open(join(folder, 'deploy.yml'), 'w') as file:
            yaml.dump(data, stream=file)
        config = 'pyon-bootstrap.yml' if bootstrap else 'pyon.yml'
        copy(join(self.template_directory, 'templates', config), join(folder, 'pyon.yml'))
        copy(join(self.template_directory, 'templates', "logging.yml"), folder)


#    def start_nodes(self):
#        if self.weather == 'cloudy':
#            self._start_nodes_cloudinitd()
#        elif self.weather == 'sunny':
#            self._start_nodes_ssh()
#        else:
#            raise ApeException("I'm not prepared for %s weather"%self.weather)
#
#    def _start_nodes_cloudinitd(self):
#        """ invoke cloudinitd to start nodes """
#        if self.state!=CONFIGURED:
#            raise ApeException('cannot start nodes when troop state is ' + self.state)
#        chdir(self.target_directory)
#        try:
#            cloudinitd(argv=['boot', 'troop-launch.conf', '-n', self.launch_name])
#            self.state=RUNNING
#        except:
#            self.state=FAILED
#
#    def _start_nodes_ssh(self):
#        pass
#
#    def stop_nodes(self):
#        """ invoke cloudinitd to stop all nodes """
#        if self.state!=RUNNING and self.state!=FAILED:
#            raise ApeException('cannot stop nodes when troop state is ' + self.state)
#        chdir(self.target_directory)
#        cloudinitd(argv=['terminate', self.launch_name])
#
#    def get_nodes_broker(self):
#        """ interrogate cloudinitd for rabbitmq parameters """
#
#        if self.state==CREATED:
#            raise ApeException('cannot query cloudinitd before Troop has been configured')
#
#        vars = {}
#        home = environ['HOME']
#
#        try:
#            cid = CloudInitD(home + '/.cloudinitd', db_name=self.launch_name, terminate=False, boot=False, ready=False)
#        except APIUsageException, e:
#            log.error("Problem loading records from cloudinit.d: %s", exc_info=True)
#            raise
#
#        svc_list = cid.get_all_services()
#        for svc in svc_list:
#            if svc.name == 'basenode':
#                vars['broker_hostname'] = svc.get_attr_from_bag("hostname")
#                vars['broker_username'] = svc.get_attr_from_bag("rabbitmq_username")
#                vars['broker_password'] = svc.get_attr_from_bag("rabbitmq_password")
#        return vars

    def get_manager(self):
        return SimpleManager(**self.get_nodes_broker())
