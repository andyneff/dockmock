FROM centos:7

#Docker+ Vars
# SPEC_NAME - the filename of the spec file, NOT PATH. It should be in the root
#             of the context
# DOCKRPM_RUN - Default bash: Command to run when the docker starts, rpmbuild 
#               to build, bash for interactive, etc...
# USER_UID - Default 1500: User id the repo files will be owned
# USER_GID - Default 1500: Group id the repo files will be owned by
#
# DOCKRPM_CUDA_INSTALL - Optional: Cuda install step

#Make this a separate line because it's so common in many of my other dockers
RUN yum groupinstall -y "Development Tools"

RUN yum install -y spectool yum-utils createrepo sudo

[{DOCKRPM_CUDA_INSTALL}]

RUN groupadd -g 1500 dev && \
    useradd -u 1500 -g 1500 dev && \
    echo "dev ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers && \
    mkdir -p ~dev/rpmbuild/SPECS ~dev/rpmbuild/BUILD ~dev/rpmbuild/BUILDROOT ~dev/rpmbuild/SOURCES ~dev/rpmbuild/SPECS ~dev/rpmbuild/RPMS ~dev/rpmbuild/SRPMS && \
    printf '[rpmdocker]\nname=rpmdocker\nbaseurl=file:///home/dev/rpmbuild/RPMS\n\
gpgcheck=0\nenabled=1\n' > /etc/yum.repos.d/rpmdocker.repo && \
    createrepo /home/dev/rpmbuild/RPMS && \
    ln -s /home/dev/rpmbuild /root/rpmbuild 
#This last line makes yum/spec commands work as root, just for ease

#End of Common Docker image

COPY source /home/dev/rpmbuild/SOURCES
COPY repo /repos
COPY gpg /gpg
COPY [{SPEC_BASENAME}] /home/dev/rpmbuild/SPECS/

RUN cp -n /repos/* /etc/yum.repos.d/ \
    cp -n /gpg/* /etc/pki/rpm-gpg/ \
    yum-builddep -y /home/dev/rpmbuild/SPECS/[{SPEC_BASENAME}]

RUN grep -v %include /home/dev/rpmbuild/SPECS/[{SPEC_BASENAME}] > /tmp/ihateperl.spec && \
    spectool -C /home/dev/rpmbuild/SOURCES/ -g -S /tmp/ihateperl.spec; \
    rm /tmp/ihateperl.spec
#Thank you stupid perl script for not supporting %include... granted, given its
#current method, it would be hard to support that, but still! > : | I bet it
#_sourcedir wasn't overwritten, it might work.

RUN groupmod -g [{USER_GID:1500}] dev && \
    usermod -u [{USER_UID:1500}] dev && \
    chown -R dev:dev /home/dev
#d+ to specific #

USER dev

#Only this first 7 lines should be moved above... In a split docker build step,
#where I can actually run it, commit, and then build part 2 starting from there.
#The trick will be Not re-running it if the previous sha and current line (sha?) 
#match, just like real existing build steps. Probably find a away to store it 
#in a label if I can
CMD if [ -d '/repos' ]; then \
      sudo cp -n /repos/* /etc/yum.repos.d/; \
    fi && \
    if [ -d '/gpg' ]; then \
      sudo cp -n /gpg/* /etc/pki/rpm-gpg/; \
    fi && \
    sudo yum-builddep -y /home/dev/rpmbuild/SPECS/[{SPEC_BASENAME}] && \
    [{DOCKRPM_RUN:bash}]
