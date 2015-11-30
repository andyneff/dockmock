#!/usr/bin/env python

import os
import types
import shutil
from subprocess import Popen as Popen_orig, PIPE, STDOUT
from glob import glob
import datetime
import re
import tempfile
from distutils.version import LooseVersion, StrictVersion
from distutils.dir_util import mkpath, copy_tree
from distutils.spawn import find_executable as which

import argparse_dissect as argparse

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

def parser():
  my_parser = argparse.ArgumentParser()
  aa = my_parser.add_argument
  aa('spec',
     help='''Name of spec. Can be just myfile or path (./specs/myfile.spec) or
             directory (./blah/myfile, for ./blah/myfile/myfile.spec')''')
  aa('--fake', nargs='?', const=True, default=False, type='bool', 
     help='Create a fake spec')
  aa('--fake_version', default='1.0.0', help="Fake version number")
  aa('--fake_arch', default=None, help="Fake arch")
  aa('--dep_check', default=True, type='bool',
     help='Skip dependency checking')
  aa('--docker_dep_check', default=False, action='store_true',
     help='Check dependencies in a docker. Slower, but does not require sudo')
  aa('--root_dir', default=os.getcwd(), help='Change root dir')
  aa('--mount_repo', default='/etc/yum.repos.d', help='emptystring to disable')
  aa('--mount_gpg', default='/etc/pki/rpm-gpg', help='empty string to disable')
  aa('--bash', default=False, action='store_true', 
     help='Run bash instead of rpmbuild')
  aa('--nvcc', default=find_nvcc())
  aa('--cuda_version')
  aa('--debug_on_fail', default=None, type='bool', const=True, nargs='?',
     help='''Commit and enter a container when the rpmbuild step fails. Default
     is to be prompted to enter''')
  aa('--quiet', default=False, type='bool', const=True, nargs='?')

  return my_parser

class DockRpm(object):
  SPEC_DIR='specs'
  RPM_DIR='rpms'
  SRPM_DIR='srpms'
  SOURCE_DIR='source'
  REPO_DIR='repos'
  GPG_DIR='gpg'
  
  def __init__(self, args=None):
    self.argv = args
    self.parser = parser()
    
    (self.args, self.extra_args) = self.parser.parse_known_args(args)

    self.root_dir = os.path.abspath(self.args.root_dir)

    # Determine path info
    self.spec_path = self.spec_path_from_arg(self.args.spec)
    self.spec_dir = os.path.dirname(self.spec_path)
    self.spec_basename = os.path.basename(self.spec_path)
    self.spec_name = os.path.splitext(self.spec_basename)[0]

    self.rpm_dir = os.path.join(self.root_dir, self.RPM_DIR)
    self.srpm_dir = os.path.join(self.root_dir, self.SRPM_DIR)
    self.source_dir = os.path.join(self.spec_dir, self.SOURCE_DIR)
    self.repo_dir = os.path.join(self.spec_dir, self.REPO_DIR)
    self.gpg_dir = os.path.join(self.spec_dir, self.GPG_DIR)

    self.code_dir = os.path.dirname(__file__)
    
    self.common_inc = os.path.join(self.root_dir, 'common.inc')
    #Should this be args.root_dir or code_dir??? I'm not sure yet
    
    self.dockerfile = os.path.join(self.spec_dir, 'Dockerfile')
    self.dockerfile_dep_check = os.path.join(self.spec_dir, 
                                             'Dockerfile_dep_check')
    
    assert not os.path.samefile(self.spec_dir, self.root_dir), \
        'If the spec dir and the root dir are the same, bad things can happen'
    assert not os.path.samefile(self.spec_dir, self.code_dir), \
        'If the spec dir and the code dir are the same, bad things can happen'
    
  def get_rpm_names_from_specfile(self, spec_path):
    cmd = ['rpm', '-q', '-D', '_sourcedir %s' % self.source_dir, 
           '--qf', '%{NAME}\t%{VERSION}\n', '--specfile', spec_path]
    pid = Popen(cmd, stdout=PIPE)
    stdout = pid.communicate()[0][:-1] #get rid of trailing newline
    pid.wait(0)
    return map(lambda x:x.split('\t'), stdout.split('\n'))

  def search_local(self, package_info):
    for spec in glob(os.path.join(self.root_dir, '*', '*.spec')):
      rpm_names = self.get_rpm_names_from_specfile(spec)
      for rpm_name in rpm_names:
        if package_info[0] == rpm_name[0]:
          if len(package_info)==1:
            return spec
          elif len(package_info)==3:
            if test_version(rpm_name[1], package_info[2], package_info[1]):
              return spec
          else:
            raise Exception('Unexpected package descriptor %s' % missing_package)

  def spec_path_from_arg(self, arg):
    arg_parts = os.path.split(arg)
    if arg_parts[0]: #has path in it
      if self.args.fake:
        if os.path.splitext(arg)[1]==os.path.extsep+'spec': #has extension
          spec_name = os.path.abspath(arg)
        else:
          spec_name = os.path.basename(arg)
          spec_name = os.path.abspath(os.path.join(arg, 
              os.path.extsep.join((spec_name, 'spec'))))
      else:
        if os.path.isdir(arg):
          spec_name = os.path.basename(arg)
          spec_name = os.path.abspath(os.path.join(arg, 
              os.path.extsep.join((spec_name, 'spec'))))
        else:
          spec_name = os.path.abspath(arg)
    else: #just name
      if os.path.splitext(arg)[1]==os.path.extsep+'spec': #has extension
        spec_name = os.path.join(self.root_dir, arg)
      else: #no extension
        spec_name = os.path.join(self.root_dir, arg, 
                                 os.path.extsep.join((arg, 'spec')))

    if not self.args.fake:
      assert os.path.isfile(spec_name), '%s does not exist' % spec_name
    else:
      assert not os.path.isfile(spec_name), \
             '%s does exists for fake' % spec_name

    return spec_name

  def create_fake(self):
    ''' Create a fake spec file '''

    if os.path.exists(self.spec_path):
      raise Exception("%s already exits, remove it or don't use --fake" % \
                      self.spec_path)
    mkpath(os.path.dirname(self.spec_path))
    with open(self.spec_path, 'w') as fid:
      fid.writeline('Name: %s' % os.path.splitext(os.path.basename(self.spec_path))[0])
      fid.writeline("License: None")
      fid.writeline("Group: Misc")
      fid.writeline("Summary: Fake rpm")
      fid.writeline("Version: %s" % self.args.fake_version)
      fid.writeline("Release: 1%{?dist}")
      if self.args.fake_arch:
        fid.writeline("BuildArch: %s" % self.args.fake_arch)
      fid.writeline("%description")
      fid.writeline("Fake Rpm")
      fid.writeline("%files")

  def dockerp(self, input_file, output_file, additional_env, inherit_env=True):
    if inherit_env:
      env = dict(os.environ)
    else:
      env = {}
    env.update(additional_env)

    if isinstance(input_file, types.StringTypes):
      input_file = open(input_file, 'r')
    if isinstance(output_file, types.StringTypes):
      if os.path.isdir(output_file):
        output_file = NamedTemporaryFile(delete=False, dir=output_file)
      else:
        output_file = open(output_file, 'w')

    Popen([os.path.join(self.code_dir, 'docker+.bsh')], 
          stdin=input_file, stdout=output_file, env=env).wait(0)

    return output_file
    
  def setup(self):
    # Prep extra files
    if self.args.fake:
      create_fake()

    mkpath(self.rpm_dir)
    mkpath(self.srpm_dir)
    mkpath(self.source_dir)
    mkpath(self.repo_dir)
    mkpath(self.gpg_dir)

    if self.args.mount_repo:
      copy_tree(self.args.mount_repo, self.repo_dir)
    if self.args.mount_gpg:
      copy_tree(self.args.mount_gpg, self.gpg_dir)

    if os.path.exists(self.common_inc):
      shutil.copy(self.common_inc, self.source_dir)
      #this this always overwrite? or never? or something inbetween?
    
    self.dockerp(os.path.join(self.code_dir, 'Dockerfile_dep_check'),
                 self.dockerfile_dep_check,
                 {'CLEAR_CACHE':str(datetime.date.today().toordinal()/5)})
    #Clear the yum cache every 5 days, this forces docker to create a new image

    # Prep repo
    if not os.path.exists(os.path.join(self.rpm_dir, 'repodata', 'repomd.xml')):
      Popen(['createrepo', self.rpm_dir]).wait(0)
    if not os.path.exists(os.path.join(self.srpm_dir, 'repodata', 'repomd.xml')):
      Popen(['createrepo', self.srpm_dir]).wait(0)

  def check_dependencies(self):
    
    image_name = 'dockrpm_%s_dep_check' % self.spec_name

    ### Build Dep Check image
    
    print 'Building dependency checking docker'
    cmd = ['docker', 'build', '-t', image_name, 
           '--quiet=true' if self.args.quiet else '--quiet=false',
           '-f', self.dockerfile_dep_check, self.spec_dir]
    Popen(cmd).wait(0)
    
    ### Run Dep Check
    print 'Checking dependencies for %s' % self.spec_path

    #Run yum-builddep
    with open(self.spec_path, 'r') as fid:
      #remove %includes cause they are just hard to handle :-\
      spec_lines = filter(lambda x: '%include' not in x, fid.readlines())

    cmd = ['docker', 'run', '-i', '--rm',
           '-v', '%s:/home/dev/rpmbuild/RPMS' % self.rpm_dir,
           '-v', '%s:/home/dev/rpmbuild/SRPMS' % self.srpm_dir,
           image_name]
    pid = Popen(cmd, stdin=PIPE, stdout=PIPE)
    stdout = pid.communicate(''.join(spec_lines))[0]
    pid.wait() #It is non-zero when packages are missing
    
    print stdout

    ###Scan for missing packages
    missing_packages = []
    error_message = 'Error: No Package found for '
    for line in stdout.split('\n'):
      if line.startswith(error_message):
        missing_packages.append(line[len(error_message):])
        
    ### Scan if local packages satisfy missing pacakges
    for missing_package in missing_packages:
      package_info = re.split('\s*([<=>]+)\s*', missing_package)
      match = self.search_local(package_info)
      if match:
        #Rerun the whole thing on each new dependency matched
        print 'Building local dependency %s' % missing_package
        #remove the spec name from the arg list and add the dependency to the 
        #arg list instead
        dep_args = [match] + argparse.filter_args(self.args, None, 'spec') 
        DockRpm(dep_args).main()
      else:
        raise Exception('No match for package %s' % missing_package)
  
  def build_docker_image(self, image_name):
    print 'Building docker image for %s' % self.spec_path
    docker_env = dict(os.environ)

    with open(os.path.join(self.args.root_dir, 'cuda'), 'r') as fid:
      if filter(lambda x:self.spec_basename in x, fid.readlines()):
        if self.args.cuda_version is None:
          pid = Popen([self.args.nvcc, '--version'], stdout=PIPE)
          stdout = pid.communicate()[0]
          pid.wait(0)
          cuda_version = stdout.splitlines()[-1].split(' ')[-1][1:]
          cuda_version = StrictVersion(cuda_version)
        else:
          cuda_version = StrictVersion(self.args.cuda_version)

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

    if self.args.bash:
      docker_env['DOCKRPM_RUN'] = 'bash'
    else:
      docker_env['DOCKRPM_RUN'] = \
          '''rpmbuild -ba -D "dist .el7" /home/dev/rpmbuild/SPECS/%s && \
             createrepo ~/rpmbuild/RPMS && \
             createrepo ~/rpmbuild/SRPMS''' % self.spec_basename

    docker_env['SPEC_BASENAME'] = self.spec_basename
    docker_env['USER_UID'] = str(os.getuid())
    docker_env['USER_GID'] = str(os.getgid())

    #docker+ the Dockerfile
    self.dockerp(os.path.join(self.code_dir, 'Dockerfile'), self.dockerfile,
                 docker_env)
    
    Popen(['docker', 'build', '-f', self.dockerfile, '-t', image_name, 
           '--quiet=true' if self.args.quiet else '--quiet=false',
           self.spec_dir]).wait(0)

  def run_docker_image(self, image_name, container_name):

    print 'Running build docker for %s' % self.spec_path
    
    #clean up incase previous attempt was dirty
    with open(os.devnull, 'w') as fid:
      if not Popen(['docker', 'inspect', container_name], 
                   stdout=fid, stderr=STDOUT).wait():
        Popen(['docker', 'rm', container_name]).wait(0)

    docker_options = []
    if self.args.mount_repo:
      docker_options += ['-v', '%s:/repos:ro' % self.args.mount_repo]
    if self.args.mount_gpg:
      docker_options += ['-v', '%s:/gpg:ro' % self.args.mount_gpg]

    pid = Popen(['docker', 'run', '-it', 
                 '-v', '%s:/home/dev/rpmbuild/RPMS' % self.rpm_dir,
                 '-v', '%s:/home/dev/rpmbuild/SRPMS' % self.srpm_dir,
                 '--name', container_name] + self.extra_args + [image_name])
    if pid.wait()==0:
      Popen(['docker', 'rm', container_name]).wait(0)
    else:
      print 'Build failed on %s. Would you like to enter a debug session? (y/n)' % container_name
      if self.args.debug_on_fail is None:
        r = str(raw_input())
        r = r.lower().startswith('y')
      else:
        r = self.args.debug_on_fail
      
      if r:
        Popen(['docker', 'commit', container_name, container_name+'_debug']).wait(0)
        Popen(['docker', 'run', '-it', 
               '-v', '%s:/home/dev/rpmbuild/RPMS' % self.rpm_dir,
               '-v', '%s:/home/dev/rpmbuild/SRPMS' % self.srpm_dir,
               '--rm', container_name+'_debug', 'bash']).wait(0)
      raise Exception('Build failed, try commiting %s and running it to debug' % container_name)

    
  def main(self):

    image_name = 'dockrpm_%s' % self.spec_name
    container_name = image_name +'_build'

    self.setup()

    if self.args.dep_check:
      self.check_dependencies()

    self.build_docker_image(image_name)

    self.run_docker_image(image_name, container_name)

    print 'Build success on %s' % self.spec_path

if __name__=='__main__':
  DockRpm().main()