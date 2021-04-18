import copy
import os
import typing as tp

from satella.coding import for_argument
from satella.json import read_json_from_file


class Configuration:
    def __init__(self, args_to_take_away: tp.Optional[tp.List[str]] = None,
                 args_to_append: tp.Optional[tp.List[str]] = None,
                 args_to_append_before: tp.Optional[tp.List[str]] = None,
                 args_to_replace: tp.Optional[tp.List[tp.Tuple[str, str]]] = None,
                 remove_non_ascii: bool = False,
                 display_before_start: bool = False):
        self.args_to_take_away = args_to_take_away or []
        self.args_to_append = args_to_append or []
        self.args_to_append_before = args_to_append_before or []
        self.args_to_replace = args_to_replace or []
        self.remove_non_ascii = remove_non_ascii
        self.display_before_start = display_before_start

    @for_argument(None, copy.copy)
    def modify(self, args):
        process, *arguments = args
        for arg_to_take_away in self.args_to_take_away:
            if arg_to_take_away in arguments:
                del arguments[arguments.index(arg_to_take_away)]

        for arg_to_append in self.args_to_append:
            if arg_to_append not in arguments:
                arguments.append(arg_to_append)

        for arg_to_append_before in self.args_to_append_before:
            if arg_to_append_before not in arguments:
                arguments = [arg_to_append_before] + arguments

        for arg_to_replace, arg_to_replace_with in self.args_to_replace:
            if arg_to_replace in arguments:
                arguments[arguments.index(arg_to_replace)] = arg_to_replace_with

        if self.remove_non_ascii:
            new_args = []

            for arg in arguments:
                new_arg = []
                for c in arg:
                    if ord(c) <= 128:
                        new_arg.append(c)
                new_args.append(''.join(new_arg))
            arguments = new_args

        if self.display_before_start:
            print('%s %s' % (process, ' '.join(arguments)))

        return [process, *arguments]

    def to_json(self):
        return {'args_to_take_away': self.args_to_take_away,
                'args_to_append': self.args_to_append,
                'args_to_append_before': self.args_to_append_before,
                'args_to_replace': self.args_to_replace,
                'remove_non_ascii': self.remove_non_ascii,
                'display_before_start': self.display_before_start}

    @classmethod
    def from_json(cls, dct):
        return Configuration(dct.get('args_to_take_away'),
                             dct.get('args_to_append'),
                             dct.get('args_to_append_before'),
                             dct.get('args_to_replace'),
                             dct.get('remove_non_ascii', False),
                             dct.get('display_before_start', False))


def load_config_for(name: str) -> Configuration:
    file_name = os.path.join('/etc/interceptor.d', name)
    if not os.path.exists(file_name):
        raise KeyError('Configuration for %s does not exist' % (name, ))

    return Configuration.from_json(read_json_from_file(file_name))
