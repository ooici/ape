
def get_logger():
    # see if pyon logger is availalbe (not guaranteed to be in PYTHONPATH)
    try:
        from pyon.util.log import log as pyon_log
        return pyon_log
    except:
        print 'pyon logging not available (check PYTHONPATH?), using built-in logging package instead.'
        from logging import Logger as builtin_logger
        return builtin_logger

log = get_logger()