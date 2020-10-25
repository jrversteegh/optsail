from __future__ import print_function

import os
import os.path
import sys
import time
import errno
from datetime import datetime

scriptdir = os.path.dirname(os.path.realpath(__file__))
_module_path = scriptdir + '/..'
print(_module_path)
sys.path.insert(0, _module_path)
sys.path.insert(0, _module_path + '/../modules/geofun')


try:
    import win32file
    win32 = True
except ImportError:
    win32 = False
    
import logging
import __main__ as main

_logname = os.path.splitext(main.__file__)[0] + '.log'

logging.basicConfig(filename=_logname, 
                    level=logging.DEBUG, 
                    filemode='w', 
                    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')

os.chdir(scriptdir)
resultsdir = scriptdir + '/results'
try:
    os.mkdir(resultsdir)
except (OSError, FileExistsError) as e:
    if e.errno != errno.EEXIST:
        print(e.errno, errno.EEXIST)
        raise e
except Exception as e:
    print(e)

log = logging.getLogger('test')
def log_line():
    log.info('==============================================')

def file_exists(filename):
    return os.path.exists(filename)

def file_age(filename):
    return time.time() - os.path.getmtime(filename)
    

log_line()
log.info('Started logging: %s' % str(datetime.now()))
log_line()

