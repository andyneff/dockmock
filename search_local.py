#!/usr/bin/env python
import sys
from glob import glob
import os
from subprocess import Popen, PIPE

def get_rpm_names_from_specfile(spec_path, source_dir):
  cmd = ['rpm', '-q', '-D', '_sourcedir %s' % source_dir, 
         '--qf', '%{NAME}\t%{VERSION}\n', '--specfile', spec_path]
  pid = Popen(cmd, stdout=PIPE)
  stdout = pid.communicate()[0][:-1] #get rid of trailing newline
  pid.wait()
  return map(lambda x:x.split('\t'), stdout.splitlines())

def search_local(specs_dir, package_name, version_test=None, version=None, package_name_suffix='_local'):
  local_pacakge_name = package_name.split('-')
  local_pacakge_names = ['-'.join(local_pacakge_name[0:x] + 
                        [local_pacakge_name[x]+package_name_suffix] + 
                        local_pacakge_name[x+1:]) 
                        for x in range(len(local_pacakge_name))]
  #I've thought about this for a while, there's no way I can determine where
  #the prefix should be added. So I just try them all, and check them all
  #example
  #[mylibrary_local, mylibrary_local-devel]
  #but what if it was my-library? then I need to check
  #[my_local-library, my-library_local, my_local-library-devel, 
  # my-library_local-devel]
  #This should work best... Hopefully no false positives.
  local_pacakge_names = [local_pacakge_name] + local_pacakge_names
  #Add it without the suffix, in the case that the suffix is already added in
  #the spec file. This is the case I want supported in the end

  print local_pacakge_names
  for spec in glob(os.path.join(specs_dir, '*', '*.spec')):
    rpm_names = get_rpm_names_from_specfile(spec, os.path.join(os.path.dirname(spec), 'source'))
    for rpm_name in rpm_names:
      if package_info[0] == rpm_name[0] or \
         any([x == rpm_name[0] for x in local_pacakge_names]):
        if version_test is None:
          return spec
        else:
          if test_version(rpm_name[1], package_info[2], package_info[1]):
            return spec

if __name__=='__main__':
  print search_local(*sys.argv[1:])