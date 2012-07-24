from os.path import join
import subprocess
from os import environ
from posix import chdir
from ape import log
from ape.common.types import ApeException
from ape.manager.troop import Troop, FAILED, RUNNING, CONFIGURED, CREATED
from cloudinitd.cli.boot import main as cloudinitd
from cloudinitd.user_api import CloudInitD
from cloudinitd.exceptions import APIUsageException, ConfigException



class CEITroop(Troop):
    def start_nodes(self):
        """ invoke cloudinitd to start nodes """
        if self.state!=CONFIGURED:
            raise ApeException('cannot start nodes when troop state is ' + self.state)
        chdir(self.target_directory)
        try:
            cloudinitd(argv=['boot', 'troop-launch.conf', '-n', self.launch_name])
            self.state=RUNNING
        except:
            self.state=FAILED

    def stop_nodes(self):
        """ invoke cloudinitd to stop all nodes """
        if self.state!=RUNNING and self.state!=FAILED:
            raise ApeException('cannot stop nodes when troop state is ' + self.state)
        chdir(self.target_directory)
        cloudinitd(argv=['terminate', self.launch_name])

    def get_nodes_broker(self):
        """ interrogate cloudinitd for rabbitmq parameters """

        if self.state==CREATED:
            raise ApeException('cannot query cloudinitd before Troop has been configured')

        vars = {}
        home = environ['HOME']

        try:
            cid = CloudInitD(home + '/.cloudinitd', db_name=self.launch_name, terminate=False, boot=False, ready=False)
        except APIUsageException, e:
            log.error("Problem loading records from cloudinit.d: %s", exc_info=True)
            raise

        svc_list = cid.get_all_services()
        for svc in svc_list:
            if svc.name == 'basenode':
                vars['broker_hostname'] = svc.get_attr_from_bag("hostname")
                vars['broker_username'] = svc.get_attr_from_bag("rabbitmq_username")
                vars['broker_password'] = svc.get_attr_from_bag("rabbitmq_password")
        return vars



class ScriptedTroop(Troop):
    """ quick and dirty implementation that relies on shell scripts """
    def start_nodes(self, launch_nodes=True):
        # start enough nodes for containers, broker, DB
        system = self.configuration['launch-name']
        count = self.get_container_count() + 2
        if launch_nodes:
            log.debug('about to start %d nodes', count)
            subprocess.check_call(['ec2-launch', str(count)])
        # start DB and broker
        log.debug('about to start db and mq services')
        subprocess.check_call(['ec2-couch', '--start', system])
        subprocess.check_call(['ec2-rabbit', '--start', system])
        # loop through pycc folders and start each
        folder_pattern = 'pycc' + self._runlevel_formatting_pattern() + '/'
        for i in xrange(1,count-1):
            folder_name = folder_pattern % i
            folder = join(self.target_directory, folder_name)
            log.debug('about to start container #%d', i)
            subprocess.check_call(['ec2-pycc', '--start', system, join(folder,'deploy.yml'), join(folder,'pyon.yml'), join(folder,'logging.yml')])

    def stop_nodes(self):
        system = self.configuration['launch-name']
        hosts = subprocess.check_output(['ec2-pycc', '--find', system]).split('\n')
        for host in hosts:
            try:
                subprocess.check_call(['ec2-pycc', '--stop', host])
                # TODO: terminate instance
            except:
                log.error('failed to stop container: ' + host)
        try:
            subprocess.check_call(['ec2-couch', '--stop', system])
            # TODO: terminate instance
        except:
            log.error('failed to stop DB server')
        try:
            subprocess.check_call(['ec2-rabbit', '--stop', system])
            # TODO: terminate instance
        except:
            log.error('failed to stop rabbit server')

    def get_nodes_broker(self):
        if self.state==CREATED:
            raise ApeException('cannot query cloudinitd before Troop has been configured')
        host = subprocess.check_output(['ec2-rabbit', '--find', self.configuration['launch-name']]).strip().split('\n')[-1]
        print 'broker is: [' + host +']'
        return { 'broker_hostname':host, 'broker_username':'guest', 'broker_password':'guest' }

