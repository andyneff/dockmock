#!/usr/bin/env python

import os
import shutil
from subprocess import Popen as Popen_orig, PIPE, STDOUT
from glob import glob
import re
import tempfile
from distutils.version import LooseVersion, StrictVersion
from distutils.dir_util import mkpath, copy_tree
from distutils.spawn import find_executable as which

import argparse_dissect as argparse

CURRENT_DIR=os.getcwd()
SPEC_DIR='specs'
RPM_DIR='rpms'
SRPM_DIR='srpms'
SOURCE_DIR='source'
REPO_DIR='repos'
GPG_DIR='gpg'

class Popen(Popen_orig):
  def __init__(self, *args, **kwargs):
    if args:
      self.cmd=args[0]
    else:
      self.cmd=kwargs['args']
    super(Popen, self).__init__(*args, **kwargs)

  def wait(self, desired_rv=None):
    rv = super(Popen, self).wait()
    if desired_rv is not None and desired_rv != rv:
      raise Exception('Expected exit code %d but got %d for %s' % (desired_rv,
                                                                   rv,
                                                                   self.cmd))
    return rv

def find_nvcc():
  nvcc = which('nvcc')
  if nvcc is None:
    nvcc = '/usr/local/cuda/bin/nvcc'
  return nvcc

def parser():
  my_parser = argparse.ArgumentParser()
  aa = my_parser.add_argument
  aa('spec',
     help='Name of spec. Can be just myfile or path (./specs/myfile.spec) or directory (./blah/myfile, for ./blah/myfile/myfile.spec')
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

def get_rpm_names_from_specfile(spec_path, source_dir):
  cmd = ['rpm', '-q', '-D', '_sourcedir %s' % source_dir, 
         '--qf', '%{NAME}\t%{VERSION}\n', '--specfile', spec_path]
  pid = Popen(cmd, stdout=PIPE)
  stdout = pid.communicate()[0][:-1] #get rid of trailing newline
  pid.wait(0)
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

def search_local(package_info, root_dir):
  for spec in glob(os.path.join(root_dir, '*', '*.spec')):
    rpm_names = get_rpm_names_from_specfile(spec, root_dir)
    for rpm_name in rpm_names:
      if package_info[0] == rpm_name[0]:
        if len(package_info)==1:
          return spec
        elif len(package_info)==3:
          if test_version(rpm_name[1], package_info[2], package_info[1]):
            return spec
        else:
          raise Exception('Unexpected package descriptor %s' % missing_package)

def spec_path_from_arg(arg, fake, root_dir):
  arg_parts = os.path.split(arg)
  if arg_parts[0]: #has path in it
    if fake:
      if os.path.splitext(arg)[1]==os.path.extsep+'spec': #has extension
        spec_name = os.path.abspath(arg)
      else:
        spec_name = os.path.basename(arg)
        spec_name = os.path.abspath(os.path.join(arg, os.path.extsep.join((spec_name, 'spec'))))
    else:
      if os.path.isdir(arg):
        spec_name = os.path.basename(arg)
        spec_name = os.path.abspath(os.path.join(arg, os.path.extsep.join((spec_name, 'spec'))))
      else:
        spec_name = os.path.abspath(arg)
  else: #just name
    if os.path.splitext(arg)[1]==os.path.extsep+'spec': #has extension
      spec_name = os.path.join(root_dir, arg)
    else: #no extension
      spec_name = os.path.join(root_dir, arg, os.path.extsep.join((arg, 'spec')))

  if not fake:
    assert os.path.isfile(spec_name), '%s does not exist' % spec_name
  else:
    assert not os.path.isfile(spec_name), '%s does exists for fake' % spec_name

  return spec_name

def create_fake(spec_path, fake_version, fake_arch=None):
  if os.path.exists(spec_path):
    raise Exception("%s already exits, remove it or don't use --fake" % \
                    spec_path)
  mkpath(os.path.dirname(spec_path))
  with open(spec_path, 'w') as fid:
    fid.writeline('Name: %s' % os.path.splitext(os.path.basename(spec_path))[0])
    fid.writeline("License: None")
    fid.writeline("Group: Misc")
    fid.writeline("Summary: Fake rpm")
    fid.writeline("Version: %s" % fake_version)
    fid.writeline("Release: 1%{?dist}")
    if fake_arch:
      fid.writeline("BuildArch: %s" % fake_arch)
    fid.writeline("%description")
    fid.writeline("Fake Rpm")
    fid.writeline("%files")

def main(args=None):
  my_parser = parser()
  (args, extra_args) = my_parser.parse_known_args(args)

  ### Determine path info
  spec_path = spec_path_from_arg(args.spec, args.fake, args.root_dir)
  spec_dir = os.path.dirname(spec_path)
  spec_basename = os.path.basename(spec_path)
  spec_name = os.path.splitext(spec_basename)[0]

  rpm_dir = os.path.join(args.root_dir, RPM_DIR)
  srpm_dir = os.path.join(args.root_dir, SRPM_DIR)
  source_dir = os.path.join(spec_dir, SOURCE_DIR)
  repo_dir = os.path.join(spec_dir, REPO_DIR)
  gpg_dir = os.path.join(spec_dir, GPG_DIR)
  
  code_dir = os.path.dirname(__file__)

  common_inc = os.path.join(args.root_dir, 'common.inc')
  #Should this be args.root_dir or code_dir??? I'm not sure yet
  
  ### Prep extra files
  
  if args.fake:
    create_fake(spec_path, args.fake_version, args.fake_arch)
  
  mkpath(rpm_dir)
  mkpath(srpm_dir)
  mkpath(source_dir)
  mkpath(repo_dir)
  mkpath(gpg_dir)
  
  if args.mount_repo:
    copy_tree(args.mount_repo, repo_dir)
  if args.mount_gpg:
    copy_tree(args.mount_gpg, gpg_dir)
    
  if os.path.exists(common_inc):
    shutil.copy(common_inc, source_dir)
    #this this always overwrite? or never? or something inbetween?
  
  # Prep repo
  
  if not os.path.exists(os.path.join(rpm_dir, 'repodata', 'repomd.xml')):
    Popen(['createrepo', rpm_dir]).wait(0)
  if not os.path.exists(os.path.join(srpm_dir, 'repodata', 'repomd.xml')):
    Popen(['createrepo', srpm_dir]).wait(0)
    
  ### Dependency checking
    
  if args.dep_check:
    print 'Checking dependencies for %s' % spec_path
    class PackageFound(Exception): #Thanks Guido for no break 2! :(
      pass

    #Run yum-builddep
    if args.docker_dep_check:
      docker_options = []

      docker_options += ['-v', '%s:/rpms' % rpm_dir]
      docker_options += ['-v', '%s:/srpms' % srpm_dir]
      if args.mount_repo:
        docker_options += ['-v', '%s:/repos' % repo_dir]
      #if args.mount_gpg:
      #  docker_options += ['-v', '%s:/gpg' % gpg_dir]

      with open(spec_path, 'r') as fid:
        #remove %includes cause they are just hard to handle :-\
        spec_lines = filter(lambda x: '%include' not in x, fid.readlines())
      cmd = ['docker', 'run', '-i', '--rm', 
             '-v', '%s:%s'%(rpm_dir,rpm_dir)] + \
            docker_options + \
            ['andyneff/rpm_dep_check']
      pid = Popen(cmd, stdin=PIPE, stdout=PIPE)
      stdout = pid.communicate(''.join(spec_lines))[0]
    else:
      #Using a docker for this is TOO slow, every check downloads ALL metadata
      #This only works if sudo is available and you are on rhel 7-ish. 
      
      #This cleans up an annoyance in the cache for the repo, so it all syncs
      Popen(['sudo', 'yum', 'clean', '--disablerepo=*', 
             '--enablerepo=rpmdocker', 'metadata']).wait(0)
      
      mock_home = os.path.join(args.root_dir, 'mock')
      mock_source = os.path.join(mock_home, 'rpmbuild', 'SOURCES')
      mkpath(mock_source)
      shutil.copy(common_inc, mock_source)
      cmd = ['sudo', 'HOME=%s' % mock_home, 'yum-builddep', '--nogpgcheck', 
             '--assumeno', spec_path]
      pid = Popen(cmd, stdout=PIPE)
      stdout = pid.communicate()[0]
    pid.wait() #It is non-zero when packages are missing

    #Scan for missing packages
    missing_packages = []
    error_message = 'Error: No Package found for '
    for line in stdout.split('\n'):
      if line.startswith(error_message):
        missing_packages.append(line[len(error_message):])
    for missing_package in missing_packages:
      package_info = re.split('\s*([<=>]+)\s*', missing_package)
      match = search_local(package_info, args.root_dir)
      if match:
        #Rerun the whole thing on each new dependency matched
        print 'Building local dependency %s' % missing_package
        #remove the spec name from the arg list and add the dependency to the 
        #arg list instead
        dep_args = package_info[0:1] + argparse.filter_args(args, None, 'spec') 
        main(dep_args)
      else:
        raise Exception('No match for package %s' % missing_package)

  ### Now to actually build the docker image
  print 'Building docker image for %s' % spec_path

  image_name = 'dockrpm_%s' % spec_name
  container_name = image_name +'_build'
  docker_env = dict(os.environ)

  with open(os.path.join(args.root_dir, 'cuda'), 'r') as fid:
    if filter(lambda x:spec_basename in x, fid.readlines()):
      if args.cuda_version is None:
        pid = Popen([args.nvcc, '--version'], stdout=PIPE)
        stdout = pid.communicate()[0]
        pid.wait(0)
        cuda_version = stdout.splitlines()[-1].split(' ')[-1][1:]
        cuda_version = StrictVersion(cuda_version)
      else:
        cuda_version = StrictVersion(args.cuda_version)

      if cuda_version >= StrictVersion('7.0'):
        docker_env['DOCKRPM_CUDA_INSTALL'] = 'RUN yum install -y ' \
            'http://developer.download.nvidia.com/compute/cuda/repos/rhel7/' \
            'x86_64/cuda-repo-rhel7-7.5-18.x86_64.rpm && ' \
            'yum install -y cuda-%d-%d' % cuda_version.version[0:2]

      elif cuda_version >= StrictVersion('5.5'): #not 100% sure this works in rhel 7 ;)
        docker_env['DOCKRPM_CUDA_INSTALL'] = 'RUN yum install -y ' \
            'http://developer.download.nvidia.com/compute/cuda/repos/rhel6/' \
            'x86_64/cuda-repo-rhel6-7.5-18.x86_64.rpm && ' \
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

  #docker+ the Dockerfile
  dockerfile = tempfile.NamedTemporaryFile(delete=False, dir=spec_dir)
  with open(os.path.join(code_dir, 'Dockerfile'), 'r') as fid:
    Popen([os.path.join(code_dir, 'docker+.bsh')], 
           stdin=fid, stdout=dockerfile, env=docker_env).wait(0)
  dockerfile.close()

  Popen(['docker', 'build', '-f', dockerfile.name, '-t', image_name, 
         spec_dir]).wait(0)
  os.remove(dockerfile.name)
  
  ### Run the acutal docker that build the rpm  
  print 'Running build docker for %s' % spec_path
  #clean up incase previous attempt was dirty
  with open(os.devnull, 'w') as fid:
    if not Popen(['docker', 'inspect', container_name], 
                 stdout=fid, stderr=STDOUT).wait():
      Popen(['docker', 'rm', container_name]).wait(0)

  docker_options = []
  if args.mount_repo:
    docker_options += ['-v', '%s:/repos:ro' % args.mount_repo]
  if args.mount_gpg:
    docker_options += ['-v', '%s:/gpg:ro' % args.mount_gpg]

  pid = Popen(['docker', 'run', '-it', 
               '-v', '%s:/home/dev/rpmbuild/RPMS' % rpm_dir,
               '-v', '%s:/home/dev/rpmbuild/SRPMS' % srpm_dir,
               '--name', container_name] + extra_args + [image_name])
  if pid.wait()==0:
    pid = Popen(['docker', 'rm', container_name])
    assert(pid.wait()==0)
  else:
    raise Exception('Build failed, try commiting %s and running it to debug' %\
                    container_name)

  print 'Build success on %s' % spec_path

if __name__=='__main__':
  main()