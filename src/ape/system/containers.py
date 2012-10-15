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

def launch_containers(config, couch, rabbit, graylog, elasticsearch):
    print '*** containers.launch_containers'
    containers = Containers(config, couch, rabbit, graylog, elasticsearch)
    containers.create_launch_plan()
    containers.launch_containers()
    return containers

def reconnect_containers(config, couch, rabbit, graylog, elasticsearch):
    print '*** containers.reconnect_containers'
    containers = Containers(config, couch, rabbit, graylog, elasticsearch)
    containers.connect_cloudinitd(must_exist=True)
    return containers

class Containers(object):
    """ a set of ExecutionEngines """
    def __init__(self, config, couch=None, rabbit=None, graylog=None, elasticsearch=None):
        self.name = config.get('containers.name')
        self.source_directory = config.get('containers.launch-plan-template')
        self.launch_plan = os.path.join('tmp', 'launch-plan', str(os.getpid()))
        # TODO: this will become a list
        self.engine_config = config.get('containers.execution-engines.0')
        self.cloud_config = config.get('containers.cloud-config')
        self.recipes = config.get('containers.recipes')
        self.couch = couch
        self.rabbit = rabbit
        self.graylog = graylog
        self.elasticsearch = elasticsearch
        self.proc = None

    def create_launch_plan(self):
        # copy launch plan into dest dir and modify config files
        shutil.copytree(self.source_directory, self.launch_plan, symlinks=False)
        # modify launch plan config
        self._modify_recipes()
        # TODO: expects exactly one execution engine -- will have to modify when multiple engines are supported
        vm_count = self.engine_config.get('nodes')
        pycc_count = self.engine_config.get('containers')
        proc_count = self.engine_config.get('processes')
        self._modify_counts(proc_count, pycc_count, vm_count)
        # copy deploy.yml and modify
        self._modify_deploy()

    def _modify_recipes(self):
        file = os.path.join(self.launch_plan, 'common', 'deps.conf')
        cfg = ConfigParser.RawConfigParser()
        cfg.read(file)
        cfg.set('deps', 'dtdata_archive_url', self.recipes)
        with open(file, 'w') as f:
            cfg.write(f)

    def _modify_counts(self, ion_procs, pycc_procs, vms):
        # 2 fields in pd.json
        pd_file = os.path.join(self.launch_plan, 'pd', 'pd.json')
        with open(pd_file, 'r') as f:
            data = json.load(f)
        data['pyon']['run_config']['config']['processdispatcher']['engines']['default']['slots'] = ion_procs
        data['pyon']['run_config']['config']['processdispatcher']['engines']['default']['base_need'] = vms
        with open(pd_file, 'w') as f:
            json.dump(data, f)
        # 1 field in eeagent_pyon.yml
        ee_file = os.path.join(self.launch_plan, 'dtrs-bootstrap', 'dt-bootstrap', 'dt', 'eeagent_pyon.yml')
        with open(ee_file, 'r') as f:
            data = yaml.load(f)
        data['contextualization']['chef_config']['pyon']['run_config']['config']['eeagent']['slots'] = ion_procs
        with open(ee_file, 'w') as f:
            yaml.dump(data, f)
        script = os.path.join(self.launch_plan, 'dtrs-bootstrap', 'prepare-tarball.sh')
        code = subprocess.call(script, shell=True)
        if code<0:
            raise Exception('failed to execute ' + script)

    def _modify_deploy(self):
        # read template
        src = self.engine_config.get('deploy-file')
        with open(src, 'r') as f:
            data = yaml.load(f)
        # keep subset of existing apps from deploy file
        config_list = self.engine_config.get('deploy-list')
        config_apps = self.engine_config.get('deploy-apps')
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
        dest = os.path.join(self.launch_plan, 'deploy.yml')
        with open(dest, 'w') as f:
            yaml.dump(data, f)
        # run rel2levels
        # HACK: have to execute with PYTHONPATH that includes YAML, so pass whatever version I'm using
        yaml_dir = os.path.dirname(os.path.dirname(yaml.__file__))
#        cmd = 'export PYTHONPATH=$PYTHONPATH:' + yaml_dir + ' ; ./rel2levels.py -c ' + self.cloud_config + ' deploy.yml -f --ignore-bootlevels > /dev/null 2>&1'
        cmd = 'export PYTHONPATH=$PYTHONPATH:' + yaml_dir + ' ; ./rel2levels.py -c ' + self.cloud_config + ' deploy.yml -f > /dev/null 2>&1'
        code = subprocess.call(cmd, shell=True, cwd=self.launch_plan)
        if code<0:
            raise Exception('failed to execute ' + cmd)

    def launch_containers(self):
#        home = os.environ['HOME']
#        file = os.path.join(self.launch_plan, self.cloud_config)
        cmd='cloudinitd boot ' + self.cloud_config + ' -n ' + self.name
        print 'executing: ' + cmd
        self.proc = subprocess.Popen(cmd, shell=True, cwd=self.launch_plan)
        # HACK: cannot launch into BG and then connect -- CloudInitD will throw exception.  so must always wait until launch completes instead
        self.proc.wait()

        file = os.path.join(self.launch_plan, self.cloud_config)
        self.connect_cloudinitd(config=file)

    def connect_cloudinitd(self, must_exist=False, config=None):
        home = os.environ['HOME']
        db_file = os.path.join(home, '.cloudinitd', 'cloudinitd-'+self.name+'.db')
        print '*** ' + db_file + ' must exist? ' + repr(must_exist)
        if must_exist and not os.path.exists(db_file):
            raise ApeException('cannot reconnect to cloudinitd -- launch does not exist')
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
