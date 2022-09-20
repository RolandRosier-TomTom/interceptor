#!{EXECUTABLE}

# Generated automatically by interceptor, a tool to intercept calls
# to the commands and to alter their arguments.

# To learn more visit https://github.com/Dronehub/interceptor

import os
import sys
from cmd_interceptor.config import load_config_for

TOOLNAME = '{TOOLNAME}'
LOCATION = '{LOCATION}'
VERSION = '{VERSION}'

if __name__ == '__main__':
    cfg = load_config_for(TOOLNAME, VERSION)
    cfg.modify_env()
    args = cfg.modify(sys.argv)
    if not cfg.has_target_forward:
        os.execv(LOCATION, args)
    else:
        args = cfg.modify_for_forward(TOOLNAME, args)
        os.execvp(args[0], args)
