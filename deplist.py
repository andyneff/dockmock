#!/usr/bin/env python
import os
import sys
import platform
from distutils.version import LooseVersion

def get_dist():
  try:
    return platform.dist()      
  except AttributeError:
    return platform.dist()

def deplist(packages=[]):
  ''' This method only really works for yum versions of fedora 

      Takes a single argument, list of package names. They can be yum names, or
      rpm filenames

      Returns two lists, first a list of dependency strings suitable for the 
      "yum install" command, and a second set of strings not currently in the
      repo, known as the local dependencies.'''
  sys.path.insert(0, '/usr/share/yum-cli') #Works in centos 7 at least
  import cli
  import yum
  base = cli.YumBaseCli()

  pkgs = []
  for package in packages:
    if (package.endswith('.rpm') and (yum.misc.re_remote_url(package) or
                                  os.path.exists(package))):
      thispkg = yum.packages.YumUrlPackage(base, base.ts, package)
      pkgs.append(thispkg)
    elif base.conf.showdupesfromrepos:
      pkgs.extend(base.pkgSack.returnPackages(patterns=[package],
                                              ignore_case=True))
    else:
      try:
        pkgs.extend(base.pkgSack.returnNewestByName(patterns=[package],
                                                    ignore_case=True))
      except yum.Errors.PackageSackError:
        pass

  results = base.findDeps(pkgs)

  deps = []
  local_deps = []

  for pkg in pkgs:
    #print 'Package', pkg.compactPrint(), 'needs'

    result = results[pkg]
    for dep in result.keys():
      if not results[pkg][dep]:
        #print 'Dep not found:', yum.misc.prco_tuple_to_string(dep)
        local_deps.append(yum.misc.prco_tuple_to_string(dep))
      else:
        #print 'Dep found:', yum.misc.prco_tuple_to_string(dep)
        deps.append(yum.misc.prco_tuple_to_string(dep))

  return deps, local_deps

def main(dep_filename='deps.txt', local_dep_filename='local_deps.txt', 
         packages=[]):
  (os_name, os_version, os_id) = get_dist()
  os_name = os_name.lower()
  os_version = LooseVersion(os_version)

  if os_name.startswith('redhat') or os_name.startswith('centos'):
    if os_version>= LooseVersion('7'):
      (deps, local_deps) = deplist(packages)
    elif os_version>= LooseVersion('6'):
      pass
    elif os_version>= LooseVersion('5'):
      pass
  if os_name.startswith('fedora'):
    pass
  if os_name.startswith('suse'):
    pass

  fid = open(dep_filename, 'w')
  local_fid = open(local_dep_filename, 'w')

  #deps should have both local and repo dependencies
  deps = deps + local_deps
  deps.sort()
  local_deps.sort()

  for dep in deps:
    fid.write(dep+'\n')

  for dep in local_deps:
    local_fid.write(dep+'\n')

if __name__=='__main__':
  #No argparse for now... Python 2.4 compat ;(
  main(sys.argv[1], sys.argv[2], sys.argv[3:])