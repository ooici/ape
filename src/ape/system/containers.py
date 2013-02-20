"""
support launching containers as defined in a YAML file
"""

import os
import shutil
import ConfigParser
import yaml
import json
import subprocess
from pprint import pprint
from cloudinitd.user_api import CloudInitD
from cloudinitd.exceptions import APIUsageException, ConfigException
from ape.manager.simple_manager import SimpleManager
from ape.common.types import ApeException
import time
from ooi.logging import log

def launch_containers(config, couch, rabbit, graylog, elasticsearch):
#    print '*** containers.launch_containers'
    containers = Containers(config, couch, rabbit, graylog, elasticsearch)
    containers.create_launch_plan()
    containers.launch_containers()
    return containers

def reconnect_containers(config, couch, rabbit, graylog, elasticsearch, cloudinitd=True):
#    print '*** containers.reconnect_containers'
    containers = Containers(config, couch, rabbit, graylog, elasticsearch)
    containers.connect_cloudinitd(must_exist=cloudinitd)
    return containers

class Containers(object):
    """ a set of ExecutionEngines

    this object wraps the launch-plans and cloudinitd portions of a container launch

    tmp/launch-plan/<pid>/plan/         result of generate-plan
                          cloud.yml     modified copy of profiles/<template>.yml.example
                          launch.yml    modified copy of res/launch/<template>.yml
    """
    def __init__(self, config, couch=None, rabbit=None, graylog=None, elasticsearch=None):
        self.config = config
        self.target_dir = os.path.join('tmp', 'launch-plan', str(os.getpid()))
        self.plan = os.path.join(self.target_dir, 'plan')
        self.name = config.get('containers.name')
        self.source_directory = config.get('containers.launch-plan')

        self.couch = couch
        self.rabbit = rabbit
        self.graylog = graylog
        self.elasticsearch = elasticsearch
        self.proc = None

    def create_launch_plan(self):
        os.makedirs(self.target_dir, mode=0755)

        # make private copy of coi-services tarball
        self._prepare_install_software()

        # copy and modify configuration of cloud resources
        self._modify_cloud_config()

        # copy and modify configuration of services and execution engines
        self._modify_launch()
        # copy deploy.yml and modify
        self._modify_deploy()
        self._generate_plan()

    def _prepare_install_software(self):
        cmd = self.config.get('containers.software.copy-command')
        if cmd:
            log.debug('executing: %s', cmd)
            subprocess.check_call(cmd, shell=True)

    def _modify_cloud_config(self):
        """ copy template cloud config file and modify """
        file = os.path.join(self.source_directory, self.config.get('containers.resource-config'))
        log.debug('configuring: %s', file)
        with open(file, 'r') as f:
            data = yaml.load(f)

        # configure appropriately
        data['iaas']['url'] = os.environ['EC2_URL']
        data['iaas']['key'] = os.environ['EC2_ACCESS_KEY']
        data['iaas']['secret'] = os.environ['EC2_SECRET_KEY']
        data['iaas']['base-image'] = self.config.get('containers.image')
        data['iaas']['base-allocation'] = self.config.get('containers.allocation')

        data['rabbitmq']['host'] = self.config.get('rabbit.hostname')
        data['rabbitmq']['username'] = self.config.get('rabbit.username')
        data['rabbitmq']['password'] = self.config.get('rabbit.password')

        data['couchdb']['host'] = self.config.get('couch.hostname')
        data['couchdb']['username'] = self.config.get('couch.username')
        data['couchdb']['password'] = self.config.get('couch.password')

        data['graylog']['host'] = self.config.get('graylog.hostname')

        url = self.config.get('containers.software.url')
        if url:
            if 'packages' not in data or not data['packages']:
                data['packages'] = {}
            data['packages']['coi_services'] = url

        if self.config.get('containers.recipes'):
            if 'packages' not in data or not data['packages']:
                data['packages'] = {}
            data['packages']['dt_data'] = self.config.get('containers.recipes')

        self.cloud_config = os.path.join(self.target_dir, 'resources.yml')
        with open(self.cloud_config, 'w') as f:
            yaml.dump(data, f, default_flow_style=False)

    def _modify_launch(self):
        file = self.config.get('containers.cloud-config')
        log.debug('configuring: %s', file)
        with open(file, 'r') as f:
            data = yaml.load(f)

        all_engines_config = self.config.get('containers.execution-engines')
        for name,engine_config in all_engines_config.iteritems():
            if name not in data['execution_engines']:
                # add new execution engine
                data['execution_engines'][name] = {}

            cfg = data['execution_engines'][name]
            for key in 'slots', 'base_need', 'replicas':
                value = engine_config.get(key)
                if value:
                    cfg[key] = value

        self.launch_config = os.path.join(self.target_dir, 'launch.yml')
        with open(self.launch_config, 'w') as f:
            yaml.dump(data, f, default_flow_style=False)

    def _modify_deploy(self):
        # read template
        src = self.config.get('services.deploy-file')
        log.debug('configuring: %s', src)
        with open(src, 'r') as f:
            data = yaml.load(f)
        # keep subset of existing apps from deploy file
        config_list = self.config.get('services.deploy-list')
        config_apps = self.config.get('services.deploy-apps')
        if config_list == '*' or (not config_list and not config_apps):
            pass # use all apps from config file (default)
        elif not config_list:
            data['apps'] = []
        elif isinstance(config_list, list):
            orig_apps = data['apps']
            data['apps'] = []
            for name in config_list:
                for app in orig_apps:
                    if app['name']==name:
                        data['apps'].append(app)
                        break
        # add explicitly configured apps
        if config_apps:
            for app in config_apps:
                data['apps'].append(app.as_dict())
        # save
        self.deploy_config = os.path.join(self.target_dir, 'deploy.yml')
        with open(self.deploy_config, 'w') as f:
            yaml.dump(data, f, default_flow_style=False)

        # OBSOLETE: no longer run rel2levels, now run generate-plan
#        # run rel2levels
#        # HACK: have to execute with PYTHONPATH that includes YAML, so pass whatever version I'm using
#        yaml_dir = os.path.dirname(os.path.dirname(yaml.__file__))
##        cmd = 'export PYTHONPATH=$PYTHONPATH:' + yaml_dir + ' ; ./rel2levels.py -c ' + self.cloud_config + ' deploy.yml -f --ignore-bootlevels > /dev/null 2>&1'
#        cmd = 'export PYTHONPATH=$PYTHONPATH:' + yaml_dir + ' ; ./rel2levels.py -c ' + self.cloud_config + ' deploy.yml -f > /dev/null 2>&1'
#        code = subprocess.call(cmd, shell=True, cwd=self.launch_plan)
#        if code<0:
#            raise Exception('failed to execute ' + cmd)

    def _generate_plan(self):
        yaml_dir = os.path.dirname(os.path.dirname(yaml.__file__))
#        pathcmd = 'export PYTHONPATH=$PYTHONPATH:' + yaml_dir
        cmd = 'bin/generate-plan --profile %s --rel %s --launch %s %s' % (
                    os.path.abspath(self.cloud_config), os.path.abspath(self.deploy_config),
                    os.path.abspath(self.launch_config), os.path.abspath(self.plan))
        log.debug('executing: %s', cmd)
        code = subprocess.call(cmd, shell=True, cwd=self.source_directory)
        if code!=0:
            raise ApeException('failed to execute ' + cmd)

    def launch_containers(self):
#        home = os.environ['HOME']
#        file = os.path.join(self.launch_plan, self.cloud_config)
        cmd='cloudinitd boot -vvv -n %s launch.conf' % self.name
#        print '====>>> about to execute: ' + cmd

        # HACK: cannot launch into BG and then connect -- CloudInitD will throw exception.  so must always wait until launch completes instead
        #self.proc = subprocess.Popen(cmd, shell=True, cwd=self.plan)
        #status = self.proc.wait()
        log.debug('executing: %s', cmd)
        subprocess.check_call(cmd, shell=True, cwd=self.plan)

        file = os.path.join(os.path.abspath(self.plan), 'launch.conf')
        self.connect_cloudinitd()

    def connect_cloudinitd(self, must_exist=False):
        config = os.path.join(os.path.abspath(self.plan), 'launch.conf')
        home = os.environ['HOME']
        db_file = os.path.join(home, '.cloudinitd', 'cloudinitd-'+self.name+'.db')
        print '*** ' + db_file + ' must exist? ' + repr(must_exist)
        if must_exist and not os.path.exists(db_file):
            raise ApeException('cannot reconnect to cloudinitd -- launch does not exist')
        elif os.path.exists(db_file):
            self.util = CloudInitD(home + '/.cloudinitd', config_file=config, db_name=self.name, boot=False, ready=False, fail_if_db_present=False)

    def wait_for_containers(self):
        print 'waiting...'
        if self.proc:
            self.proc.wait()
            self.proc = None
#        self.util.block_until_complete(poll_period=2)


    def get_manager(self):
        return SimpleManager(**self.get_nodes_broker())

    def get_nodes_broker(self):
        """ interrogate cloudinitd for rabbitmq parameters """
        vars = {}
        svc_list = self.util.get_all_services()
        for svc in svc_list:
            if svc.name == 'basenode':
                vars['broker_hostname'] = svc.get_attr_from_bag("hostname")
                vars['broker_username'] = svc.get_attr_from_bag("rabbitmq_username")
                vars['broker_password'] = svc.get_attr_from_bag("rabbitmq_password")
        return vars

    def get_process_list(self):
        cmd='ceictl -n %s process list' % self.name
#        print '====>>> about to execute: ' + cmd

        # HACK: cannot launch into BG and then connect -- CloudInitD will throw exception.  so must always wait until launch completes instead
        #self.proc = subprocess.Popen(cmd, shell=True, cwd=self.plan)
        #status = self.proc.wait()
        processes = [ ]
        current = { }
        log.debug('executing: %s', cmd)
        lines = iter(subprocess.check_output(cmd, shell=True).split('\n'))
        try:
            while True:
                line = lines.next()
                if line:
                    fields = line.split('=')
                    name = fields[0].strip()
                    value = fields[1].strip()
                    if name=='Process ID':
                        if current:
                            processes.append(current)
                            current = { }
                    elif name=='Process Name':
                        idlen = len(value.split('-')[-1])
                        type = value[0:-idlen-1]
                        current['type'] = type
                    current[name] = value
        except StopIteration:
            pass
        return processes


