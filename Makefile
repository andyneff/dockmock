SHELL := /usr/bin/env bash

FIX_DEP_ARG = --assumeno

ARGS = --debug-on-fail=false

SPECS = $(wildcard specs/*/*.spec)
PHONY_TARGETS = all install clean rpmdocker.repo cache purge repos check_dep fix_dep build

DRYRUN = 0

ifneq "$(DRYRUN)" "0"
DR = echo
else
DR =
endif

.PHONY: $(PHONY_TARGETS) $(SPECS)

RECURSE := 0

all:
	$(MAKE) build $(SPECS)
	#$(MAKE) build $$(ls specs/*/*.spec | grep -E '/(.*)/\1\.spec' | sed -r 's|.*/(.+)/\1\.spec|\1|')

build:
	$(eval RECURSE := 1)
	@for target in $(filter-out $(PHONY_TARGETS),$(MAKECMDGOALS)); do \
	  echo "Building $${target}"; \
	  $(DR) ./dockrpm $(ARGS) $${target} || break; \
	done

yum:
	$(eval RECURSE := 1)
	$(DR) yum install --enablerepo rpmdocker $(filter-out $(PHONY_TARGETS),$(MAKECMDGOALS))

%:
	@if [ "$(RECURSE)" == 0 ]; then $(MAKE) RECURSE=1 build $@; fi

$(SPECS):
	@if [ "$(RECURSE)" == 0 ]; then $(MAKE) RECURSE=1 build $@; fi

rpmdocker.repo:
	echo "[rpmdocker]" > rpmdocker.repo
	echo "name=rpmdocker" >> rpmdocker.repo
	echo "baseurl=file://`pwd`/rpms" >> rpmdocker.repo
	echo "gpgcheck=0" >> rpmdocker.repo
	echo "enabled=0" >> rpmdocker.repo
	echo "metadata_expire=0" >> rpmdocker.repo
	echo "metadata_expire_filter=never" >> rpmdocker.repo

install: rpmdocker.repo
	cp rpmdocker.repo /etc/yum.repos.d/

repo:
	createrepo rpms
	createrepo srpms


cache:
	$(DR) yum clean --disablerepo='*' --enablerepo=rpmdocker metadata
	if [ "$$(id -u)" == "0" -a "$${SUDO_UID}" != "" -a "$${SUDO_UID}" != "0" ]; then \
	  $(DR) sudo -u \#$${SUDO_UID} $(MAKE) cache; \
	fi

purge: clean
	$(DR) rm -rf rpms srpms

clean:
	$(DR) rm -f rpmdocker.repo

check_dep:
	$(DR) yum remove --assumeno `yumdb search from_repo rpmdocker | \grep '^\w' | \grep -v "Loaded plugins"`

fix_dep:
	while IFS='' read -r line || [[ -n "$$line" ]]; do\
	  if [ "$$(echo $$line | awk '{print $$4}')" != "@rpmdocker" ]; then\
	    package=$$(echo $$line | awk '{print $$1}');\
	    echo "Broken package $$package"... Fixing;\
	    $(DR) yum install $(FIX_DEP_ARG) $$(rpm -qR  $$package | \grep -v ^rpmlib\( | sed 's/\([^ ]*\).*/\1/') || :;\
	  fi;\
	done < <(yum remove -q --assumeno $$(yumdb search from_repo rpmdocker | \grep '^\w' | \grep -v "Loaded plugins") 2>&1 | \grep '^ \w' | head -n -1 | tail -n +2)
