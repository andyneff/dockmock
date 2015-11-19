FROM centos:7

#Make this a separate line because it's so common in many of my other dockers
RUN yum groupinstall -y "Development Tools"

RUN yum install -y spectool yum-utils createrepo

RUN groupadd -g 1500 dev && \
    useradd -u 1500 -g 1500 dev && \
    mkdir -p ~dev/rpmbuild/SPECS ~dev/rpmbuild/BUILD ~dev/rpmbuild/BUILDROOT ~dev/rpmbuild/SOURCES ~dev/rpmbuild/SPECS ~dev/rpmbuild/RPMS ~dev/rpmbuild/SRPMS && \
    printf '[rpmdocker]\nname=rpmdocker\nbaseurl=file:///home/dev/rpmbuild/RPMS\n\
gpgcheck=0\nenabled=1\n' > /etc/yum.repos.d/rpmdocker.repo && \
    createrepo /home/dev/rpmbuild/RPMS && \
    ln -s /home/dev/rpmbuild /root/rpmbuild 
#This last line makes yum/spec commands work as root, just for ease

#End of Common Docker image

COPY common.inc /home/dev/rpmbuild/SOURCES/
COPY [{SPEC_BASENAME}] /home/dev/rpmbuild/SPECS/


RUN yum-builddep -y /home/dev/rpmbuild/SPECS/*

RUN for filename in $(ls /home/dev/rpmbuild/SPECS/*); do\
      grep -v %include $filename > /tmp/ihateperl.spec && \
      spectool -C /home/dev/rpmbuild/SOURCES/ -g -S /tmp/ihateperl.spec; \
    done && \
    rm /tmp/ihateperl.spec
#Thank you stupid perl script for not supporting %include... granted, given its
#current method, it would be hard to support that, but still! > : | I bet it
#_sourcedir wasn't overwritten, it might work.

RUN groupmod -g [{GID}] dev && \
    usermod -u [{UID}] dev && \
    chown -R dev:dev /home/dev
#d+ to specific #

USER dev

CMD rpmbuild -ba -D "dist .el7" -D "_topdir /home/dev/rpmbuild/" /home/dev/rpmbuild/SPECS/* && \
    createrepo ~/rpmbuild/RPMS && \
    createrepo ~/rpmbuild/SRPMS
