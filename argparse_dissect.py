import argparse
from argparse import *

import sys as _sys

def custom_call(self, parser, namespace, values, option_string=None):
    if not '_ordered_args_names' in namespace:
      setattr(namespace, '_ordered_args_names', list())
      setattr(namespace, '_ordered_args_option_strings', list())
      setattr(namespace, '_ordered_args_values', list())
    namespace._ordered_args_names.append(self.dest)
    namespace._ordered_args_option_strings.append(self.option_strings)
    namespace._ordered_args_values.append(values)

def str2bool(v):
  #susendberg's function
  return v.lower() in ("yes", "y", "true", "t", "1")

class OrderedAction(object):
  ''' Helper mixin for creating ordered actions

      This class must be inherited first so that the MRO order for __call__ 
      works '''
  def __call__(self, parser, namespace, values, option_string=None):
    if not '_ordered_args_names' in namespace:
      setattr(namespace, '_ordered_args_names', list())
      setattr(namespace, '_ordered_args_option_strings', list())
      setattr(namespace, '_ordered_args_values', list())
    namespace._ordered_args_names.append(self.dest)
    namespace._ordered_args_option_strings.append(self.option_strings)
    namespace._ordered_args_values.append(values)
    super(OrderedAction, self).__call__(parser, namespace, values, option_string)

#Action=type('Action', (OrderedAction, argparse.Action), {})
#This won't work. The user will have to do class NewAction(OrderedAction, Action) :(
_StoreAction=type('_StoreAction', 
                  (OrderedAction, argparse._StoreAction), {})
_StoreTrueAction=type('_StoreTrueAction', 
                  (OrderedAction, argparse._StoreTrueAction), {})
_StoreConstAction=type('_StoreConstAction', 
                  (OrderedAction, argparse._StoreConstAction), {})
_StoreFalseAction=type('_StoreFalseAction', 
                  (OrderedAction, argparse._StoreFalseAction), {})
_AppendAction=type('_AppendAction', 
                  (OrderedAction, argparse._AppendAction), {})
_AppendConstAction=type('_AppendConstAction', 
                  (OrderedAction, argparse._AppendConstAction), {})
_CountAction=type('_CountAction', 
                  (OrderedAction, argparse._CountAction), {})
_HelpAction=type('_HelpAction', 
                  (OrderedAction, argparse._HelpAction), {})
_VersionAction=type('_VersionAction', 
                  (OrderedAction, argparse._VersionAction), {})
_SubParsersAction=type('_SubParsersAction', 
                  (OrderedAction, argparse._SubParsersAction), {})

class ArgumentParser(argparse.ArgumentParser):
  def __init__(self, *args, **kwargs):
    super(ArgumentParser, self).__init__(*args, **kwargs)

    self.register('type', 'bool', str2bool)

    self._registries['action'] = {} #To remind me I need to code the rest
    self.register('action', None, _StoreAction)
    self.register('action', 'store', _StoreAction)
    self.register('action', 'store_true', _StoreTrueAction)
    self.register('action', 'store_const', _StoreConstAction)
    self.register('action', 'store_false', _StoreFalseAction)
    self.register('action', 'append', _AppendAction)
    self.register('action', 'append_const', _AppendConstAction)
    self.register('action', 'count', _CountAction)
    self.register('action', 'help', _HelpAction)
    self.register('action', 'version', _VersionAction)
    self.register('action', 'parsers', _SubParsersAction)

def filter_args(namespace, args=None, exclude=[]):
  if args is None:
    args = _sys.argv[1:]

  if not isinstance(exclude, (list, tuple, set)):
    exclude = [exclude]

  filtered_args = []
  #filtered_args2 = [] 
  #never trust this, it won't work in more complicated situations
  index = 0
  for arg_name, flag, values in zip(namespace._ordered_args_names,
                                    namespace._ordered_args_option_strings,
                                    namespace._ordered_args_values):
    
    if not isinstance(values, (list, tuple, set)):
      values = [values]
    #canonicalize

    if arg_name in exclude:
      index += len(flag)
      index += len(values)
      continue

    #filtered_args2.extend(flag)
    #if isinstance(values, list):
    #  filtered_args2.extend(values)
    #else:
    #  filtered_args2.append(values)

    filtered_args.extend(args[index:index+len(flag)])
    index += len(flag)

    filtered_args.extend(args[index:index+len(values)])
    index += len(values)

  return filtered_args