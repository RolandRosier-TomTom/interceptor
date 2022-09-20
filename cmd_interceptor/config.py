import copy
import os
import sys
import typing as tp
import warnings

import pkg_resources
from satella.coding import for_argument
from satella.json import read_json_from_file, write_json_to_file


class Configuration:
    _base_path = None
    _interceptor_path = None

    @classmethod
    def project_name(cls) -> str:
        return 'cmd-interceptor'

    @classmethod
    def base_path(cls) -> str:
        if cls._base_path is None:
            env_virt_env = os.environ.get("VIRTUAL_ENV")
            if env_virt_env is None:
                cls._base_path = '/etc'
            else:
                cls._base_path = os.path.join(env_virt_env, 'etc')

        return cls._base_path

    @classmethod
    def interceptor_path(cls) -> str:
        if cls._interceptor_path is None:
            cls._interceptor_path = os.path.join(cls.base_path(),
                                                 'cmd_interceptor.d')

        return cls._interceptor_path

    @property
    def path(self) -> str:
        return os.path.join(self.interceptor_path(), self.app_name)

    def __init__(self, args_to_disable: tp.Optional[tp.List[str]] = None,
                 args_to_append: tp.Optional[tp.List[str]] = None,
                 args_to_prepend: tp.Optional[tp.List[str]] = None,
                 args_to_replace: tp.Optional[tp.List[tp.Tuple[str, str]]] = None,
                 display_before_start: bool = False,
                 notify_about_actions: bool = False,
                 envs_to_add: tp.Optional[tp.List[tp.Tuple[str, str]]] = None,
                 fwd_to_target: tp.Optional[tp.Dict[str, tp.Any]] = None,
                 app_name: tp.Optional[str] = None,
                 deduplication: bool = False,
                 log: bool = False):
        self.args_to_disable = args_to_disable or []
        self.args_to_append = args_to_append or []
        self.args_to_prepend = args_to_prepend or []
        self.args_to_replace = args_to_replace or []
        self.display_before_start = display_before_start
        self.notify_about_actions = notify_about_actions
        self.envs_to_add = envs_to_add or []
        self.fwd_to_target = fwd_to_target or {}
        self.app_name = app_name
        self.deduplication = deduplication
        self.log = log

    @property
    def has_target_forward(self) -> bool:
        does_have_target_forward = False
        if (self.fwd_to_target is not None and
                "host_fwd_cmd" in self.fwd_to_target and
                self.fwd_to_target["host_fwd_cmd"] and
                "target_fwd_cmd" in self.fwd_to_target and
                self.fwd_to_target["target_fwd_cmd"]):
            does_have_target_forward = True

        return does_have_target_forward

    def to_json(self):
        return {'args_to_disable': self.args_to_disable,
                'args_to_append': self.args_to_append,
                'args_to_prepend': self.args_to_prepend,
                'args_to_replace': self.args_to_replace,
                'display_before_start': self.display_before_start,
                'notify_about_actions': self.notify_about_actions,
                'deduplication': self.deduplication,
                'log': self.log}

    @for_argument(None, copy.copy)
    def modify(self, args, *extra_args):
        process, *arguments = args
        for arg_to_take_away in self.args_to_disable:
            while arg_to_take_away in arguments:
                if self.notify_about_actions:
                    print('interceptor(%s): taking away %s' % (self.app_name, arg_to_take_away))
                del arguments[arguments.index(arg_to_take_away)]

        for arg_to_replace, arg_to_replace_with in self.args_to_replace:
            while arg_to_replace in arguments:
                if self.notify_about_actions:
                    print('interceptor(%s): replacing %s with %s' % (self.app_name, arg_to_replace,
                                                                     arg_to_replace_with))
                arguments[arguments.index(arg_to_replace)] = arg_to_replace_with

        for arg_to_append in self.args_to_append:
            if arg_to_append not in arguments:
                if self.notify_about_actions:
                    print('interceptor(%s): appending %s' % (self.app_name, arg_to_append))
                arguments.append(arg_to_append)

        for arg_to_prepend in reversed(self.args_to_prepend):
            if arg_to_prepend not in arguments:
                if self.notify_about_actions:
                    print('interceptor(%s): prepending %s' % (self.app_name, arg_to_prepend))
                arguments = [arg_to_prepend] + arguments

        if self.deduplication:
            new_arguments = []
            added_args = {}
            for arg in arguments:
                if arg not in added_args:
                    new_arguments.append(arg)
                    added_args.add(arg)
            arguments = new_arguments

        if self.display_before_start:
            print('%s %s' % (sys.argv[0], ' '.join(arguments)))

        if self.log:
            if not os.path.exists('/var/log/interceptor.d'):
                os.mkdir('/var/log/interceptor.d')
            with open(os.path.join('/var/log/interceptor.d', sys.argv[0], 'a')) as f_out:
                f_out.write(' '.join(arguments))

        return [process, *arguments]

    def modify_env(self):
        for env_to_add, value_of_env_var in self.envs_to_add:
            if env_to_add not in os.environ:
                if self.notify_about_actions:
                    print('interceptor(%s): adding env var %s with value %s'
                          % (self.app_name, env_to_add, value_of_env_var))
                os.environ[env_to_add] = value_of_env_var

    @staticmethod
    def substitute_fwd_replacements(fwd_replacements):
        fwd_reps = fwd_replacements
        replaced = []
        for rep in fwd_replacements:
            replacee = rep[0]
            replacement = str(eval(rep[1]))
            replaced.append([replacee, replacement])

        return replaced

    def modify_for_forward(self, cmd_name, args, *extra_args):
        old_process, *arguments = args
        process = self.fwd_to_target["host_fwd_cmd"]
        replacements = self.substitute_fwd_replacements(
            self.fwd_to_target["fwd_replacements"])
        host_args = None
        if (self.fwd_to_target["host_fwd_cmd_args"] is not None and
                self.fwd_to_target["host_fwd_cmd_args"]):
            host_args = []
            for arg in self.fwd_to_target["host_fwd_cmd_args"]:
                this_arg = arg
                for replacement_arr in replacements:
                    replacee = '${' + replacement_arr[0] + '}'
                    replacement = replacement_arr[1]
                    this_arg = this_arg.replace(replacee, replacement)
                host_args.append(this_arg)
        target_fwd_cmd = self.fwd_to_target["target_fwd_cmd"]
        target_fwd_args = None
        if (self.fwd_to_target["target_fwd_args"] is not None and
                self.fwd_to_target["target_fwd_args"]):
            target_fwd_args = self.fwd_to_target["target_fwd_args"]
        target_fwd_prefix = None
        if (self.fwd_to_target["target_fwd_prefix"] is not None and
                self.fwd_to_target["target_fwd_prefix"]):
            target_fwd_prefix = self.fwd_to_target["target_fwd_prefix"]
        target_cmd_to_run = []
        for val in [target_fwd_prefix, cmd_name, *arguments]:
            if val is not None:
                target_cmd_to_run.append(val)
        target_cmd_to_run_as_str = "" + ' '.join(target_cmd_to_run) + ""
        target_args = []
        target_args_list = []
        if target_fwd_args is not None:
            target_args_list = [target_fwd_cmd, *target_fwd_args,
                                target_cmd_to_run_as_str]
        else:
            target_args_list = [target_fwd_cmd, target_cmd_to_run_as_str]
        for val in target_args_list:
            if val is not None:
                target_args.append(val)

        return_list = []
        if host_args is not None:
            return_list = [process, *host_args, *target_args]
        else:
            return_list = [process, *target_args]

        return return_list

    def save(self):
        write_json_to_file(self.path, self.to_json(), sort_keys=True, indent=4)

    @classmethod
    def from_json(cls, dct, app_name: str):
        prepend = dct.get('args_to_prepend')
        if prepend is None:
            prepend = dct.get('args_to_append_before')
            if prepend is not None:
                warnings.warn('args_to_append_before is deprecated, use args_to_prepend',
                              DeprecationWarning)
        take_away = dct.get('args_to_disable')
        if take_away is None:
            take_away = dct.get('args_to_take_away')
            if take_away is not None:
                warnings.warn('args_to_take_away is deprecated, use args_to_prepend',
                              DeprecationWarning)

        return Configuration(take_away,
                             dct.get('args_to_append'),
                             prepend,
                             dct.get('args_to_replace'),
                             dct.get('display_before_start', False),
                             dct.get('notify_about_actions', False),
                             dct.get('envs_to_add'),
                             dct.get('fwd_to_target'),
                             app_name=app_name,
                             deduplication=dct.get('deduplication', False),
                             log=dct.get('log', False))


def assert_correct_version(version: str) -> None:
    if version == '':
        # print('You have used an older version of interceptor to intercept this command.\n'
        #       'It is advised to undo the interception and reintercept the call to upgrade.')
        return
    my_version = pkg_resources.require(Configuration.project_name())[0].version
    if int(version.split('.')[0]) > int(my_version.split('.')[0]):
        sys.stderr.write('You have intercepted this call using a higher version of Interceptor. \n'
                         'This might not work as advertised. Try undo\'ing the interception \n'
                         'and intercepting this again.\n'
                         'Aborting.')
        sys.exit(1)


def load_config_for(name: str, version: tp.Optional[str] = '') -> Configuration:
    if version is not None:
        assert_correct_version(version)

    file_name = os.path.join(Configuration.interceptor_path(), name)
    if not os.path.isfile(file_name):
        print('Configuration for %s does not exist or is not a file' % (name,))
        sys.exit(1)

    cfg = Configuration.from_json(read_json_from_file(file_name), app_name=name)
    return cfg
