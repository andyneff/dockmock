# RPM Building in Dockers #

This package accomplishes three tasks

1. Builds an rpm in a pristine docker, similar to https://github.com/alanfranz/docker-rpm-builder
2. Allows one of your rpms to depend on another
3. K.I.S.S.

Right now only Centos 7 is considered

Other OSes will not be an immediate focus, CUDA support will be

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

```spec
%include %{_sourcedir}/common.inc
Source999: common.inc

%define real_name my_software

Name: %{real_name}_l
```

This also means when 