""" logging module for ape

    unfortunately, pyon logging has hooks into all kinds of things,
    so a simple import of pyon logging causes the test to fail
    if all of the other container configuration files are not in place!

    so first check if we are inside of a capability container,
    and if so import pyon logging.
    otherwise, use simple python logging
"""

# capability container defines global reference to itself...
if 'cc' in dir():
    from pyon.public import log
else:
    from logging import getLogger
    log = getLogger('ape')
