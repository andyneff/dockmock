

.PHONY: all install clean rpmdocker.repo clean_repo

all:

rpmdocker.repo:
	echo "[rpmdocker]" > rpmdocker.repo
	echo "name=rpmdocker" >> rpmdocker.repo
	echo "baseurl=file://`pwd`/rpms" >> rpmdocker.repo
	echo "gpgcheck=0" >> rpmdocker.repo
	echo "enabled=1" >> rpmdocker.repo

install: rpmdocker.repo
	cp rpmdocker.repo /etc/yum.repos.d/

clean_repo:
	yum clean --disablerepo='*' --enablerepo=rpmdocker metadata
	sudo yum clean --disablerepo='*' --enablerepo=rpmdocker metadata

clean:
	rm -f specs/tmp??????
	rm rpmdocker.repo