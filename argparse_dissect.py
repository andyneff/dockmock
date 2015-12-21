#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
from argparse import *

import sys as _sys
import os

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

def get_config(option_strings=['--conf'], safe_eval=False, args=None, **kwargs):
  ''' Get just a config argument out of an argparse object

      Creates a single argument parser and trys to parse just --conf (or 
      option_strings) to determine the configuration file. The files is loaded
      and parsed into a dictionary. The keys should be dest names that match up
      with your argument parser, and the expressions will be evaluate

      Optional Arguments:
      option_strings - A list of strings send to add_argument as the option 
                       strings. Default is ['--conf']. This should also be
                       added to your real argument parser since the arguments
                       are not removed.
      safe_eval - True or False, should the expressions be evaluated with 
                  ast.literal_eval (True) or eval(False). Use safe_eval when
                  you do not have ABSOLUTE TRUST that you want to give whomever
                  generated the conf file complete control to your python which
                  probably is the same as saying full access to your computer,
                  unless you are in a sandbox or similar.
      args - List of arguments to parse. Default is None, meaning use sys.argv
      **kwargs - Other kwargs to send to add_argument for whatever reason. 
                 Maybe you want to specify a default config file, etc...

      Return value:
      dictionary of dest names and default values

      Config file layout:
        dest_name1˽expression\n
        dest_name2˽expression\n

      Example:
      >> my_parser.add_argument('--dog',...)
      >> my_parser.add_argument('--cat',...)
      >> my_parser.add_argument('mog',...)

      Config file example:
        dog 15
        cat 17*21
        mog [11, 22, 33]

      Note: cat in this example only works if save_eval is false. The other two 
      always work.'''
  if 'default' not in kwargs:
    kwargs['default'] = None

  parser = argparse.ArgumentParser(add_help=False)
  parser.add_argument(*option_strings, dest='config_file', **kwargs)
  (args, unknown) = parser.parse_known_args(args)
  if args.config_file and os.path.exists(args.config_file):
    try:
      with open(args.config_file, 'r') as fid:
        lines = [line.strip().split(' ', 1) for line in fid.readlines()]
      if safe_eval:
        import ast
        return {k:ast.literal_eval(v) for (k,v) in lines}
      else:
        return {k:eval(v) for (k,v) in lines}
    except:
      print "Error parsing", args.config_file
  return {}

def replace_defaults(parser, defaults):
  ''' Replace the default values of parser with values from defaults

      The keys from defaults are matched up with dest fields in parser, and 
      replace the default values. Works in simple cases, haven't found a case 
      where it doesn't work

      Arguments:
      parser - An ArgumentParser, with the arguments already added
      defaults - dict like the one created from get_config

      Suggestion:
      Use %(default)s in the help text to use the new default values'''

  for action in parser._actions:
    for (key,value) in defaults.iteritems():
      if action.dest == key:
        action.default = value


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