''' simple test file to try out the troop definition/start/stop

    for better example, see demo6
'''

from ape.manager.troop import Troop

TROOP_CONFIGURATION_FILE = 'test/resources/test_parse.trp'

def main():
    t = Troop(clobber=True)
    t.configure(TROOP_CONFIGURATION_FILE)
    print 'have troop: ' + repr(t)
    print '# services: %d' % len(t.services)
    print '# node types: %d' % len(t.node_types)
    print '--------------------------'
    for node_type in t.node_types:
        print 'type: %s\n' % str(node_type)
    print '--------------------------'

    print '\n\n\ncreating launch plan'
    t.create_launch_plan()

    agent_name = t.configuration['agent-service']['name']
    print 'agent service name: %s' % agent_name
    print 'agent service: %s' % repr(t.service_by_name[agent_name])

    print 'starting troop'
    t.start_nodes()
    print 'stopping troop'
    t.stop_nodes()

if __name__=="__main__":
    main()