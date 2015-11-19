# Support for long double
%define disable_long_double 0
%ifarch %{arm}
  %define disable_long_double 1
%endif

# Configuration of MPI backends
%ifnarch %{ix86} x86_64
  # No MPICH2 support except on x86 and x86_64
  %bcond_with mpich2
%else
  %bcond_without mpich2
%endif

%ifarch s390 s390x
  # No OpenMPI support on zseries
  %bcond_with openmpi
%else
  %bcond_without openmpi
%endif

%include %{_sourcedir}/common.inc

Name:		boost
Version:	1.59.0
%define stupid_version %(echo %{version} | sed 's|\\.|_|g' -)
Release:	1%{?dist}
Summary:	The free peer-reviewed portable C++ source libraries
Source:		http://sourceforge.net/projects/%{name}/files/%{name}/%{version}/boost_1_59_0.tar.bz2
Source999:        common.inc

License:	Boost
Group:		System Environment/Libraries
URL: 		http://sodium.resophonic.com/boost-cmake/%{version}.cmake0/
BuildRoot: 	%{_tmppath}/%{name}-%{version}-root

BuildRequires: libstdc++-devel%{?_isa}
BuildRequires: bzip2-devel%{?_isa}
BuildRequires: zlib-devel%{?_isa}
BuildRequires: python-devel%{?_isa}
%if %{with python3}
BuildRequires: python3-devel%{?_isa}
%endif
BuildRequires: libicu-devel%{?_isa}
BuildRequires: chrpath


%description
Boost provides free peer-reviewed portable C++ source libraries.  The
emphasis is on libraries which work well with the C++ Standard
Library, in the hopes of establishing "existing practice" for
extensions and providing reference implementations so that the Boost
libraries are suitable for eventual standardization. (Some of the
libraries have already been proposed for inclusion in the C++
Standards Committee's upcoming C++ Standard Library Technical Report.)

%prep
%setup -q -n %{name}_%{stupid_version}

%build
./bootstrap.sh --with-python=%{__python} \
               --libdir=%{_libdir} --prefix=%{_prefix} \
               --includedir=%{_includedir}

#I have to set LD_LIBRARY_PATH, and I have NO IDEA WHY
env LD_LIBRARY_PATH="${LD_LIBRARY_PATH}${LD_LIBRARY_PATH:+:}%{_libdir}" \
    ./b2 %{_smp_mflags} -d2 --target=shared,static

%install
[ "$RPM_BUILD_ROOT" != "/" ] && rm -rf $RPM_BUILD_ROOT

./b2 install --prefix=${RPM_BUILD_ROOT}%{cat_prefix} \
             --exec-prefix=${RPM_BUILD_ROOT}%{cat_exec_prefix} \
             --libdir=${RPM_BUILD_ROOT}%{_libdir} \
             --includedir=${RPM_BUILD_ROOT}%{_includedir}

%clean
[ "$RPM_BUILD_ROOT" != "/" ] && rm -rf $RPM_BUILD_ROOT

%files
%defattr(-,root,root)
%exclude /usr/lib/debug
%{_includedir}/boost
%{_libdir}/*


