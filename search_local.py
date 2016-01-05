#!/usr/bin/env python
import sys
from glob import glob
import os
from subprocess import Popen, PIPE
import shutil
from distutils.dir_util import mkpath

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


def get_rpm_names_from_specfile(spec_path, source_dir):
  cmd = ['rpm', '-q', '-D', '_sourcedir %s' % source_dir, 
         '--qf', '%{NAME}\t%{VERSION}\n', '--specfile', spec_path]
  pid = Popen(cmd, stdout=PIPE, stderr=PIPE)
  stdout = pid.communicate()[0][:-1] #get rid of trailing newline
  pid.wait()
  return map(lambda x:x.split('\t'), stdout.splitlines())

def search_local(package_name, version_test=None, version=None, specs_dir='/specs', package_name_suffix='_local'):
  #I think the package_name_suffix feature should be removed now...
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
  local_pacakge_names = [package_name] + local_pacakge_names
  #Add it without the suffix too, in the case that the suffix is already added
  #in the spec file, or something. This is the case I want supported in the 
  #end

  for spec in glob(os.path.join(specs_dir, '*', '*.spec')):
    temp_common_inc = False
    common_inc = os.path.join(os.path.dirname(spec), 'source', 'common.inc')
    if not os.path.exists(common_inc):
      mkpath(os.path.dirname(common_inc))
      shutil.copy(os.path.join(specs_dir, 'common.inc'), common_inc)
      temp_common_inc = True
    rpm_names = get_rpm_names_from_specfile(spec, os.path.join(os.path.dirname(spec), 'source'))
    if temp_common_inc:
      os.remove(common_inc)
    for rpm_name in rpm_names:
      if package_name == rpm_name[0] or \
         any([x == rpm_name[0] for x in local_pacakge_names]):
        if version_test is None:
          return os.path.relpath(spec, specs_dir)
        else:
          if test_version(rpm_name[1], package_version, package_test):
            return os.path.relpath(spec, specs_dir)

if __name__=='__main__':
  print search_local(*sys.argv[1:])