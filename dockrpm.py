#!/usr/bin/env python

import os
from subprocess import Popen, PIPE, STDOUT
from glob import glob
import re
import tempfile
from distutils.version import LooseVersion, StrictVersion
from distutils.dir_util import mkpath
from distutils.spawn import find_executable as which

import argparse_dissect as argparse

CURRENT_DIR=os.getcwd()
SPEC_DIR='specs'
RPM_DIR='rpms'
SRPM_DIR='srpms'
SOURCE_DIR='sources'

def find_nvcc():
  nvcc = which('nvcc')
  if nvcc is None:
    nvcc = '/usr/local/cuda/bin/nvcc'
  return nvcc

def parser():
  my_parser = argparse.ArgumentParser()
  aa = my_parser.add_argument
  aa('spec',
     help='Name of spec. Can be just myfile or path (./specs/myfile.spec)')
  aa('--fake', default=False, action='store_true', help='Create a fake spec')
  aa('--fake_version', default='1.0.0', help="Fake version number")
  aa('--fake_arch', default=None, help="Fake arch")
  aa('--dep_check', default=True, type='bool',
     help='Skip dependency checking')
  aa('--docker_dep_check', default=False, action='store_true',
     help='Check dependencies in a docker. Slower, but does not require sudo')
  aa('--root_dir', default=CURRENT_DIR, help='Change root dir')
  aa('--mount_repo', default='/etc/yum.repos.d', help='emptystring to disable')
  aa('--mount_gpg', default='/etc/pki/rpm-gpg', help='empty string to disable')
  aa('--bash', default=False, action='store_true', 
     help='Run bash instead of rpmbuild')
  aa('--nvcc', default=find_nvcc())
  aa('--cuda_version')

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

def search_local(package_info, local_spec_dir):
  for spec in glob(os.path.join(local_spec_dir, '*.spec')):
    rpm_names = get_rpm_names_from_specfile(spec, local_spec_dir)
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
  my_parser = parser()
  (args, extra_args) = my_parser.parse_known_args(args)

  if args.fake:
    if os.path.splitext(args.spec)[1]: #if extension
      spec_filename = os.path.abspath(args.spec)
    else:
      spec_filename = os.path.join(args.root_dir, SPEC_DIR, 
                                   os.path.extsep.join((args.spec, 'spec')))

    if os.path.exist(spec_filename):
      raise Exception("%s already exits, remove it or don't use --fake" % \
                      spec_filename)

    mkpath(os.path.dirname(spec_filename))
    with open(spec_filename, 'w') as fid:
      fid.writeline('Name: %s' % os.path.splitext(os.path.basename(spec_filename))[0])
      fid.writeline("License: None")
      fid.writeline("Group: Misc")
      fid.writeline("Summary: Fake rpm")
      fid.writeline("Version: %s" % args.fake_version)
      fid.writeline("Release: 1%{?dist}")
      if args.fake_arch:
        fid.writeline("BuildArch: %s" % args.fake_arch)
      fid.writeline("%description")
      fid.writeline("Fake Rpm")
      fid.writeline("%files")
  else:
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

  mkpath(rpm_dir)
  mkpath(srpm_dir)
  mkpath(source_dir)

  if not os.path.exists(os.path.join(rpm_dir, 'repodata', 'repomd.xml')):
    assert(Popen(['createrepo', rpm_dir]).wait()==0)
  if not os.path.exists(os.path.join(srpm_dir, 'repodata', 'repomd.xml')):
    assert(Popen(['createrepo', srpm_dir]).wait()==0)

  docker_options = []

  docker_options += ['-v', '%s:/rpms' % rpm_dir]
  docker_options += ['-v', '%s:/srpms' % srpm_dir]
  if args.mount_repo:
    docker_options += ['-v', '%s:/repos:ro' % args.mount_repo]
  if args.mount_gpg:
    docker_options += ['-v', '%s:/gpg:ro' % args.mount_gpg]

  if args.dep_check:
    print 'Checking dependencies for %s' % spec_filename
    class PackageFound(Exception):
      pass

    #Run yum-builddep
    if args.docker_dep_check:
      with open(spec_filename, 'r') as fid:
        cmd = ['docker', 'run', '-i', '--rm', 
               '-v', '%s:%s'%(rpm_dir,rpm_dir)] + \
              docker_options + \
              ['andyneff/rpm_dep_check']
        pid = Popen(cmd, stdin=PIPE, stdout=PIPE)
        stdout = pid.communicate(fid.read())[0]
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
    #assert(pid.wait()==0) It is non-zero when packages are missing
    pid.wait()

    #Scan for missing pacakges
    missing_packages = []
    for line in stdout.split('\n'):
      if line.startswith('Error: No Package found for '):
        missing_packages.append(line[len('Error: No Package found for '):])
    for missing_package in missing_packages:
      package_info = re.split('\s*([<=>]+)\s*', missing_package)
      match = search_local(package_info, spec_dir)
      if match:
        dep_args = argparse.filter_args(args, None, 'spec')
        print 'Building local dependency %s' % missing_package
        dep_args = package_info[0:1] + dep_args
        main(dep_args)
        if not args.docker_dep_check:
          pid = Popen(['sudo', 'yum', 'clean', '--disablerepo=*', 
                       '--enablerepo=rpmdocker', 'metadata'])
          assert(pid.wait()==0)
      else:
        raise Exception('No match for package %s' % missing_package)

  print 'Building docker image for %s' % spec_filename

  spec_basename = os.path.basename(spec_filename)
  spec_name = os.path.splitext(spec_basename)[0]
  image_name = 'dockrpm_%s' % spec_name
  container_name = image_name +'_build'

  docker_env = dict(os.environ)

  with open(os.path.join(spec_dir, 'cuda'), 'r') as fid:
    if filter(lambda x:spec_basename in x, fid.readlines()):
      if args.cuda_version is None:
        pid = Popen([args.nvcc, '--version'], stdout=PIPE)
        stdout = pid.communicate()[0]
        assert(pid.wait()==0)
        cuda_version = stdout.splitlines()[-1].split(' ')[-1][1:]
        cuda_version = StrictVersion(cuda_version)
      else:
        cuda_version = StrictVersion(args.cuda_version)

      if cuda_version >= StrictVersion('7.0'):
        docker_env['DOCKRPM_CUDA_INSTALL'] = 'RUN yum install -y ' \
            'http://developer.download.nvidia.com/compute/cuda/repos/rhel7/' \
            'x86_64/cuda-repo-rhel7-7.5-18.x86_64.rpm epel-release && ' \
            'yum install -y cuda-%d-%d' % cuda_version.version[0:2]

      elif cuda_version >= StrictVersion('5.5'): #not 100% sure this works in rhel 7 ;)
        docker_env['DOCKRPM_CUDA_INSTALL'] = 'RUN yum install -y ' \
            'http://developer.download.nvidia.com/compute/cuda/repos/rhel6/' \
            'x86_64/cuda-repo-rhel6-7.5-18.x86_64.rpm epel-release && ' \
            'yum install -y cuda-%d-%d' % cuda_version.version[0:2]
      else:
        raise Exception('Unsupported version of CUDA %s' % cuda_version)

  if args.bash:
    docker_env['DOCKRPM_RUN'] = 'bash'
  else:
    docker_env['DOCKRPM_RUN'] = \
        '''rpmbuild -ba -D "dist .el7" /home/dev/rpmbuild/SPECS/%s && \
           createrepo ~/rpmbuild/RPMS && \
           createrepo ~/rpmbuild/SRPMS''' % spec_basename
  
  docker_env['SPEC_BASENAME'] = spec_basename
  docker_env['USER_UID'] = str(os.getuid())
  docker_env['USER_GID'] = str(os.getgid())

  dockerfile = tempfile.NamedTemporaryFile(delete=False, dir=spec_dir)

  with open(os.path.join(args.root_dir,'Dockerfile'), 'r') as fid:
    pid = Popen([os.path.join(args.root_dir, 'docker+.bsh')], 
                stdin=fid, stdout=dockerfile, env=docker_env)
    assert(pid.wait()==0)
  dockerfile.close()

  pid=Popen(['docker', 'build', '-f', dockerfile.name, '-t', image_name, 
             spec_dir])
  assert(pid.wait()==0)
  os.remove(dockerfile.name)

  print 'Running build docker for %s' % spec_filename
  #clean up incase previous attempt was dirty
  with open(os.devnull, 'w') as fid:
    if not Popen(['docker', 'inspect', container_name], 
             stdout=fid, stderr=STDOUT).wait():
      pid = Popen(['docker', 'rm', container_name])
      assert(pid.wait()==0)

  docker_options = []
  if args.mount_repo:
    docker_options += ['-v', '%s:/repos:ro' % args.mount_repo]
  if args.mount_gpg:
    docker_options += ['-v', '%s:/gpg:ro' % args.mount_gpg]

  pid = Popen(['docker', 'run', '-it', 
               '-v', '%s:/home/dev/rpmbuild/RPMS' % rpm_dir,
               '-v', '%s:/home/dev/rpmbuild/SRPMS' % srpm_dir,
               '-v', '%s:/home/dev/rpmbuild/SOURCES' % source_dir,
               '--name', container_name] + extra_args + [image_name])
  if pid.wait()==0:
    pid = Popen(['docker', 'rm', container_name])
    assert(pid.wait()==0)
  else:
    raise Exception('Build failed, try commiting %s and running it to debug' %\
                    container_name)

  print 'Build success on %s' % spec_filename

if __name__=='__main__':
  main()