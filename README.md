# RPM Building in Dockers #

This package accomplishes three tasks

1. Builds an rpm in a pristine docker, similar to https://github.com/alanfranz/docker-rpm-builder
2. Allows one of your rpms to depend on another
3. K.I.S.S.

Right now only Centos 7 is considered

Other OSes will not be an immediate focus, CUDA support will be

## Install ##

```
git clone ? .
sudo make install
```

Now the rpmdocker repo has been installed, but disabled by default to prevent 
the OS from trying to use this repository to satisfy dependencies. There is 
still a risk, but this helps.

```
sudo make check_dep
```

Look for any packages NOT from the rpmdocker repo.

If you find any, and want to know why, look for lines in the `Resolving Dependencies`
section that start with `--> Processing Dependency`, for example:

```
Resolving Dependencies
--> Running transaction check
---> Package boost_local.x86_64 0:1.58.0-8.el7 will be erased
---> Package boost_local-atomic.x86_64 0:1.58.0-8.el7 will be erased
--> Processing Dependency: boost-atomic = 1.53.0-23.el7 for package: boost-1.53.0-23.el7.x86_64
---> Package boost_local-chrono.x86_64 0:1.58.0-8.el7 will be erased
---> Package boost_local-context.x86_64 0:1.58.0-8.el7 will be erased
...
```

**Note**: Only the first reason for the dependency is listed. In this case, 
`boost-chrono-1.53.0-23.el7.x86_64` is also needed, etc... So instead of fixing each
dependency of `boost-1.53.0-23.el7.x86_64` one at a time, next 

```
yum install $(rpm -qR  boost | \grep -v ^rpmlib\( | sed 's/\([^ ]*\).*/\1/')

```

An automatic check can be previewed with `sudo make fix_dep` and automatically 
run with `sudo make fix_dep FIX_DEP_ARG=-y`


## Arguments ##

1 - Spec filename (or basename without extension)
2 - (Optional) 1 for interactive bash instead of build

## Environment Variable ## 

NVCC - 
DOCKRPM_FAKE  -
DOCKRPM_FAKE_ARCH - 
DOCKRPM_FAKE_VERSION -
DOCKRPM_MOUNT_REPO -
DOCKRPM_MOUNT_GPG -
RUN_DEP_CHECK -
RUN_DEP_CHECK_DOCKER - Run Dependency check in Docker or Locally on host
## Special dirs ##

/repos
/gpg

## Writing RPMs ##

To alleviate OS conflicts, always

```spec
%include %{_sourcedir}/common.inc
Source999:        common.inc
%define real_name softwarename
Name:             %{real_name}_local
Provides:         %{real_name}
```

Most likely `%prep` will look like 

```spec
%prep
%setup -q -n %{real_name}-%{version}
```

Make sure you always add _local for two reasons. 

1. It needs to be different so that yum doesn't do stupid things. While rpm is
smart enough to do the right thing, yum is NOT. The suffix is needed for yum
2. _local is added to packages names when dockrpm.py is searching for which
spec needs to be build. This is part of the automated dependency checking and
building. Unfortunately the `rpm -q --specfile` command does not list `--provides`
with the `--qf` flag ;(

This also means when 

You can `Obsoletes: %{name}-blah`
You should `Provides: %{real_name}-blah`

That way, all you need is

`Requires: RealName-blah`, no _local. This works because of the `Provides:` line

## Troubleshooting ##

It IS possible that installing these rpms could satisfy a dependency for an OS
package dependency. To check this, run 