SHELL := /usr/bin/env bash

FIX_DEP_ARG = --assumeno

.PHONY: all install clean rpmdocker.repo cache_repo clean_rpms repos

all:

rpmdocker.repo:
	echo "[rpmdocker]" > rpmdocker.repo
	echo "name=rpmdocker" >> rpmdocker.repo
	echo "baseurl=file://`pwd`/rpms" >> rpmdocker.repo
	echo "gpgcheck=0" >> rpmdocker.repo
	echo "enabled=0" >> rpmdocker.repo

install: rpmdocker.repo
	cp rpmdocker.repo /etc/yum.repos.d/

repo:
	createrepo rpms
	createrepo srpms

cache_repo:
	yum clean --disablerepo='*' --enablerepo=rpmdocker metadata
	sudo yum clean --disablerepo='*' --enablerepo=rpmdocker metadata

clean_rpms:
	rm -rf rpms srpms

clean:s
	rm rpmdocker.repo

check_dep:
	yum remove --assumeno `yumdb search from_repo rpmdocker | \grep '^\w' | \grep -v "Loaded plugins"`

fix_dep:
	while IFS='' read -r line || [[ -n "$$line" ]]; do\
	  if [ "$$(echo $$line | awk '{print $$4}')" != "@rpmdocker" ]; then\
	    package=$$(echo $$line | awk '{print $$1}');\
	    echo "Broken package $$package"... Fixing;\
	    yum install $(FIX_DEP_ARG) $$(rpm -qR  $$package | \grep -v ^rpmlib\( | sed 's/\([^ ]*\).*/\1/') || :;\
	  fi;\
	done < <(yum remove -q --assumeno $$(yumdb search from_repo rpmdocker | \grep '^\w' | \grep -v "Loaded plugins") 2>&1 | \grep '^ \w' | head -n -1 | tail -n +2)