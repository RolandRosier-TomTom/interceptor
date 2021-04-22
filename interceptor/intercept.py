import json
import os
import shutil
import sys

import pkg_resources
from satella.coding import silence_excs
from satella.files import write_to_file, read_in_file

from interceptor.config import load_config_for, Configuration
from interceptor.whereis import filter_whereis

INTERCEPTED = '-intercepted'


def intercept(tool_name: str) -> None:
    source_file = pkg_resources.resource_filename(__name__, 'templates/cmdline.py')
    try:
        load_config_for(tool_name)
    except KeyError:
        print('No configuration found for %s, creating a default one' % (tool_name, ))
        shutil.copy(pkg_resources.resource_filename(__name__, 'templates/config'),
                    os.path.join('/etc/interceptor.d', tool_name))
    source = filter_whereis(sys.argv[1])
    target_intercepted = source+INTERCEPTED
    if os.path.exists(target_intercepted):
        print('Target already intercepted. Aborting.')
        sys.exit(1)
    shutil.copy(source, target_intercepted)
    os.unlink(source)
    source_content = read_in_file(source_file, 'utf-8')
    source_content = source_content.format(EXECUTABLE=sys.executable,
                                           TOOLNAME=tool_name,
                                           LOCATION=target_intercepted,
                                           VERSION=pkg_resources.require('interceptor')[0].version)
    write_to_file(source, source_content, 'utf-8')
    os.chmod(source, 0o555)
    print('Successfully intercepted %s' % (tool_name, ))


def is_intercepted(app_name: str) -> bool:
    path = filter_whereis(app_name)
    return os.path.exists(path) and os.path.exists(path+INTERCEPTED) \
           and os.path.exists(os.path.join('/etc/interceptor.d', app_name))


def unintercept(app_name: str) -> None:
    source = filter_whereis(app_name + INTERCEPTED)
    src_name = source[:-len(INTERCEPTED)]
    os.unlink(src_name)
    shutil.move(source, src_name)
    print('Successfully unintercepted %s' % (app_name, ))
    print('Leaving the configuration in place')


def assert_intercepted(app_name: str):
    if not is_intercepted(app_name):
        print('%s is not intercepted' % (app_name,))
        sys.exit(1)


def banner():
    print('''Unrecognized command. Usage:
    * intercept foo - intercept foo
    * intercept undo foo - cancel intercepting foo
    * intercept configure foo - type in the configuration for foo in JSON format, end with Ctrl+D
    * intercept show foo - show the configuration for foo
    * intercept display foo - enable displaying what is launched on foo's startup
    * intercept hide foo - disable displaying what is launched on foo's startup
    * intercept edit foo - launch a nano/vi to edit it's configuration
    * intercept append foo ARG - add ARG to be appended to command line whenever foo is ran
    * intercept prepend foo ARG - add ARG to be prepended to command line whenever foo is ran
    * intercept disable foo ARG - add ARG to be eliminated from the command line whenever foo is ran
    * intercept replace foo ARG1 ARG2 - add ARG1 to be replaced with ARG2 whenever it is passed to foo
    * intercept notify foo - display a notification each time an argument action is taken
    * intercept unnotify foo - hide the notification each time an argument action is taken
    * intercept link foo bar - symlink bar's config file to that of foo
    * intercept reset foo - reset foo's configuration (delete it and create a new one)
    ''')


def run():
    if not os.path.exists('/etc/interceptor.d'):
        print('/etc/interceptor.d does not exist, creating...')
        os.mkdir('/etc/interceptor.d')

    if len(sys.argv) == 2:
        intercept(sys.argv[1])
    elif len(sys.argv) >= 3:
        op_name = sys.argv[1]
        app_name = sys.argv[2]

        if op_name == 'undo':
            assert_intercepted(app_name)
            unintercept(app_name)
        elif op_name == 'status':
            if is_intercepted(app_name):
                print('%s is intercepted' % (app_name, ))
            else:
                print('%s is NOT intercepted' % (app_name, ))
        elif op_name == 'configure':
            assert_intercepted(app_name)
            data = sys.stdin.read()
            try:
                json.loads(data)
            except json.JSONDecoder:
                print('Configuration is invalid JSON')
                sys.exit(1)
            write_to_file(os.path.join('/etc/interceptor.d', app_name), data, 'utf-8')
            print('Configuration successfully written')
        elif op_name == 'show':
            assert_intercepted(app_name)
            config = read_in_file(os.path.join('/etc/interceptor.d', app_name), 'utf-8')
            print(config)
        elif op_name == 'edit':
            assert_intercepted(app_name)
            editor = filter_whereis('nano', abort_on_failure=False)
            if editor is None:
                editor = filter_whereis('vi')
            os.execv(editor, [editor, os.path.join('/etc/interceptor.d', app_name)])
        elif op_name in ('append', 'prepend', 'disable', 'replace', 'display', 'hide',
                         'notify', 'unnotify'):
            assert_intercepted(app_name)
            cfg = load_config_for(app_name)
            if op_name == 'append':
                cfg.args_to_append.append(sys.argv[3])
            elif op_name == 'prepend':
                cfg.args_to_prepend.append(sys.argv[3])
            elif op_name == 'disable':
                cfg.args_to_disable.append(sys.argv[3])
            elif op_name == 'replace':
                cfg.args_to_replace.append([sys.argv[3], sys.argv[4]])
            elif op_name == 'display':
                cfg.display_before_start = True
            elif op_name == 'hide':
                cfg.display_before_start = False
            elif op_name == 'notify':
                cfg.notify_about_actions = True
            elif op_name == 'unnotify':
                cfg.notify_about_actions = False
            cfg.save()
            print('Configuration changed')
        elif op_name == 'link':
            source = os.path.join('/etc/interceptor.d', app_name)
            target = os.path.join('/etc/interceptor.d', sys.argv[3])
            with silence_excs(IOError):
                os.unlink(target)
            os.system('ln -s %s %s' % (source, target))
            print('Linked %s to read from %s''s config' % (sys.argv[3], app_name))
        elif op_name == 'reset':
            os.unlink(os.path.join('/etc/interceptor.d', app_name))
            cfg = Configuration()
            cfg.app_name = app_name
            cfg.save()
            print('Configuration reset')
        else:
            print('Unrecognized command %s' % (op_name, ))
            banner()
            sys.exit(1)
    else:
        banner()
