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
# ENABLE_LOCAL - By default, when building the docker image, the local rpm repo
#                is not used when building the image, but only when running the
#                image. I believe this to be best, because it keeps my
#                intermediate work out of the docker image, thus making running
#                a build step reflect the current state of my local repo ONLY
#                and not some halfway in between "When I build that image last
#                week, it had that package that was slightly different than it
#                is now" situation

#Make this a separate line because it's so common in many of my other dockers
RUN yum groupinstall -y "Development Tools"

RUN yum install -y spectool yum-utils createrepo sudo which
#Had to add which because the new Centos 7.2.1511 because it's missing for rpmbuild :(

[{DOCKRPM_CUDA_INSTALL}]

RUN groupadd -g 1500 dev && \
    useradd -u 1500 -g 1500 dev && \
    echo "dev ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers && \
    sed -i '/requiretty/d' /etc/sudoers && \
    mkdir -p ~dev/rpmbuild/{SPECS,BUILD,BUILDROOT,SPECS,SOURCES,RPMS,SRPMS} && \
    printf '[rpmdocker]\nname=rpmdocker\nbaseurl=file:///home/dev/rpmbuild/RPMS\n\
gpgcheck=0\nenabled=1\n' > /etc/yum.repos.d/rpmdocker.repo && \
    createrepo /home/dev/rpmbuild/RPMS && \
    ln -s /home/dev/rpmbuild /root/rpmbuild 
#This last line makes yum/spec commands work as root, just for ease

#End of Common Docker image

COPY repos /repos
COPY gpg /gpg
COPY deps.txt /home/dev/rpmbuild/deps.txt

RUN (cp -n /repos/* /etc/yum.repos.d/ || :) && \
    (cp -n /gpg/* /etc/pki/rpm-gpg/ || :) && \
    if [ -s /home/dev/rpmbuild/deps.txt ]; then \
      yum install [{ENABLE_LOCAL:--disablerepo=rpmdocker}] -y $(cat /home/dev/rpmbuild/deps.txt) || :; \
    fi
    #This line is expected to install all remote rpms, and NOT any of the local
    #rpms. There is a change that ALL rpms are local, and none will be installed.
    #This is why || : is added.

COPY curl.bsh /home/dev/rpmbuild/curl.bsh
RUN cd /home/dev/rpmbuild/SOURCES && \
    chmod 755 /home/dev/rpmbuild/curl.bsh && sync && \
    /home/dev/rpmbuild/curl.bsh
#A more manual version of the following, WITHOUT depending on the spec file directly
#My hope is that I can change the spec file, and as long as curl.bsh does not 
#change, neither with the sha :)

RUN (groupmod -g [{USER_GID:50}] dev || usermod -g [{USER_GID:50}] dev) && \
    usermod -u [{USER_UID:1000}] dev && \
    chown -R dev:dev /home/dev
#d+ to specific #

USER dev

ENV DOCKRPM_DEBUG=0 DOCKRPM_BASH=0

COPY rpmmacros /home/dev/.rpmmacros
COPY source /home/dev/rpmbuild/SOURCES
COPY [{SPEC_BASENAME}] /home/dev/rpmbuild/SPECS/


CMD if [ "${DOCKRPM_DEBUG}" == "0" ]; then \
      sudo yum clean --disablerepo=* --enablerepo=rpmdocker metadata && \
      eval RPMBUILD_ARGS=(${RPMBUILD_ARGS}) && \
      srpm_name=$(rpmbuild -bs /home/dev/rpmbuild/SPECS/[{SPEC_BASENAME}] \
          -D "_srcrpmdir /tmp" "${RPMBUILD_ARGS[@]}" | \grep "^Wrote: " | \
          sed 's/Wrote: \(.*\)/\1/') && \
      srpm_name2=$(echo $srpm_name | sed 's|nosrc|src|') && \
      if [ "$srpm_name" != "$srpm_name2" ]; then \
        mv $srpm_name $srpm_name2; \
      fi && \
      #Thank you https://bugzilla.redhat.com/show_bug.cgi?id=1166126 :(
      sudo yum-builddep -y ${srpm_name2} ; \
    fi && \
    if [ "${DOCKRPM_BASH}" == "1" ]; then \
      echo "When you are ready, run:" && \
      echo "rpmbuild -ba ${RPMBUILD_ARGS[@]} /home/dev/rpmbuild/SPECS/[{SPEC_BASENAME}]" && \
      bash; \
    else \
      rpmbuild -ba "${RPMBUILD_ARGS[@]}" /home/dev/rpmbuild/SPECS/[{SPEC_BASENAME}] && \
      createrepo ~/rpmbuild/RPMS -o /tmp && \
      rm -rvf ~/rpmbuild/RPMS/repodata && \
      mv /tmp/repodata ~/rpmbuild/RPMS/ && \
      createrepo ~/rpmbuild/SRPMS -o /tmp && \
      rm -rvf ~/rpmbuild/SRPMS/repodata && \
      mv /tmp/repodata ~/rpmbuild/SRPMS/; \
    fi
    
#Run yum-builddep, only this time it should catch all the local rpms that 
#weren't installed in the last yum install command