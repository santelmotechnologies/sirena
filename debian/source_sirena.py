'''apport package hook for sirena.

Code adapted from the novacut project.

(c) 2012 Novacut Inc
Author: Jason Gerard DeRose <jderose@novacut.com>
'''

import os
from os import path

from apport.hookutils import attach_file_if_exists

LOGS = (
    ('DebugLog', 'log'),
)

def add_info(report):
    report['CrashDB'] = 'sirena'
    sirena_dir = path.join(os.environ['HOME'], '.config', 'sirena', 'Logs')
    for (key, name) in LOGS:
        log = path.join(sirena_dir, name)
        attach_file_if_exists(report, log, key)
