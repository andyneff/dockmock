#!/usr/bin/env python

import os
from subprocess import Popen, PIPE
from glob import glob
import re
from distutils.version import LooseVersion, StrictVersion
from distutils.dir_util import mkpath

import argparse_dissect as argparse

CURRENT_DIR=os.getcwd()
SPEC_DIR='specs'
RPM_DIR='rpms'
SRPM_DIR='srpms'
SOURCE_DIR='sources'

def parser():
  my_parser = argparse.ArgumentParser()
  aa = my_parser.add_argument
  aa('spec',
     help='Name of spec. Can be just myfile or path (./specs/myfile.spec)')
  aa('--fake', default=False, action='store_true', help='Create a fake spec')
  aa('--dep_check', default=True, type='bool',
     help='Skip dependency checking')
  aa('--docker_dep_check', default=False, action='store_true',
     help='Check dependencies in a docker. Slower, but does not require sudo')
  aa('--root_dir', default=CURRENT_DIR, help='Change root dir')
  aa('--mount_repo', default='/etc/yum.repos.d', help='emptystring to disable')
  aa('--mount_gpg', default='/etc/pki/rpm-gpg', help='empty string to disable')

  return my_parser

def get_rpm_names_from_specfile(spec_filename, source_dir):
  cmd = ['rpm', '-q', '-D', '_sourcedir %s' % source_dir, 
         '--qf', '%{NAME}\t%{VERSION}\n', '--specfile', spec_filename]
  pid = Popen(cmd, stdout=PIPE)
  stdout = pid.communicate()[0][:-1] #get rid of trailing newline
  return map(lambda x:x.split('\t'), stdout.split('\n'))

def test_version(version1, version2, test):
  try:
    v1 = StrictVersion(version1)
    v2 = StrictVersion(version2)
  except:
    v1 = LooseVersion(version1)
    v2 = LooseVersion(version2)

  if test=='=':
    return v1==v2
  elif test=='<':
    return v1<v2
  elif test=='>':
    return v1>v2
  elif test=='<=':
    return v1<=v2
  elif test=='>=':
    return v1>=v2
  else:
    raise Exception('Unexpected logic test %s' % test)

def search_local(package_info, local_spec_dir, local_source_dir):
  for spec in glob(os.path.join(local_spec_dir, '*.spec')):
    rpm_names = get_rpm_names_from_specfile(spec, local_source_dir)
    for rpm_name in rpm_names:
      if package_info[0] == rpm_name[0]:
        if len(package_info)==1:
          return spec
        elif len(package_info)==3:
          if test_version(rpm_name[1], package_info[2], package_info[1]):
            return spec
        else:
          raise Exception('Unexpected package descriptor %s' % missing_package)

def main(args=None):
  if args is None:
    my_parser = parser()
    args = my_parser.parse_args()
 
  if os.path.exists(args.spec):
    spec_filename = os.path.abspath(args.spec)
  else:
    spec_filename = os.path.join(args.root_dir, SPEC_DIR, os.path.extsep.join((args.spec, 'spec')))

  if not os.path.exists(spec_filename) and not args.fake:
    raise Exception('Spec file %s does not exist' % spec_filename)
  elif os.path.exists(spec_filename) and args.fake:
    raise Exception('Spec file %s exists for fake generation' % spec_filename)

  rpm_dir = os.path.join(args.root_dir, RPM_DIR)
  srpm_dir = os.path.join(args.root_dir, SRPM_DIR)
  spec_dir = os.path.join(args.root_dir, SPEC_DIR)
  source_dir = os.path.join(args.root_dir, SOURCE_DIR)

  docker_options = []

  docker_options += ['-v', '%s:/rpms' % rpm_dir]
  docker_options += ['-v', '%s:/srpms' % srpm_dir]
  docker_options += ['-v', '%s:/home/dev/rpmbuild/SOURCES' % source_dir]
  if args.mount_repo:
    docker_options += ['-v', '%s:/repos:ro' % args.mount_repo]
  if args.mount_gpg:
    docker_options += ['-v', '%s:/gpg:ro' % args.mount_gpg]

  if args.dep_check:
    class PackageFound(Exception):
      pass

    if args.docker_dep_check:
      with open(spec_filename, 'r') as fid:
        cmd = ['docker', 'run', '-i', '--rm', 
               '-v', '%s:%s'%(rpm_dir,rpm_dir)] + \
              docker_options + \
              ['andyneff/rpm_dep_check']
        pid = Popen(cmd, stdin=PIPE, stdout=PIPE)
        stdout = pid.communicate(fid.read())[0]
        print stdout
    else:
      mock_home = os.path.join(args.root_dir, 'mock')
      mkpath(os.path.join(mock_home, 'rpmbuild'))
      try:
        os.symlink(spec_dir, os.path.join(mock_home, 'rpmbuild', 'SOURCES'))
      except:
        pass
      cmd = ['sudo', 'HOME=%s' % mock_home, 'yum-builddep', '--nogpgcheck', 
             '--assumeno', spec_filename]
      pid = Popen(cmd, stdout=PIPE)
      stdout = pid.communicate()[0]
    pid.wait()

    missing_packages = []
    for line in stdout.split('\n'):
      if line.startswith('Error: No Package found for '):
        missing_packages.append(line[len('Error: No Package found for '):])
    for missing_package in missing_packages:
      package_info = re.split('\s*([<=>]+)\s*', missing_package)
      match = search_local(package_info, spec_dir, source_dir)
      if match:
        print match
      else:
        raise Exception('No match for package %s' % missing_package)

if __name__=='__main__':
  main()