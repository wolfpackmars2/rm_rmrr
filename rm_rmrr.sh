#!/bin/sh -
#======================================================================================================================
# vim: softtabstop=4 shiftwidth=4 expandtab fenc=utf-8 spell spelllang=en cc=120
#======================================================================================================================
#
#          FILE: pve-rm_rmrr.sh
#
#   DESCRIPTION: Create RMRR patch for latest PVE (Proxmox) kernel
#                Min Requirements: CPU Cores >= 4; 4GiB RAM
#                Rec Requirements: Quad Core CPU with HT or better; 16GiB RAM or greater
#                OS: Mac or Linux
#                Requires Oracle Virtualbox and Hashicorp Vagrant
#
#          BUGS: github.com/wolfpackmars2
#
#     COPYRIGHT: (c) 2019 S. Groesz
#
#  ORGANIZATION: GROESZ
#       CREATED: 2019.07.09
#======================================================================================================================
set -o nounset                              # Treat unset variables as an error

__ScriptName="rm_rmrr.sh"
__ScriptFullName="$0"
__ScriptArgs="$*"

_OPTIONS="x"
_LONGOPTIONS="no-vagrant"
_VAGRANT_VM_CORES=`grep -c ^processor /proc/cpuinfo`
_VAGRANT_VM_CORES=`expr $_VAGRANT_VM_CORES - 2`
_VAGRANT_VM_NAME="HPRMRRPATCH"
_VAGRANT_VM_BOX="ubuntu/bionic64"
_VAGRANTFILE_DIR="`pwd`"

# Bootstrap script truth values
BS_TRUE=1
BS_FALSE=0

__LogFile=$BS_FALSE
_ECHO_DEBUG=${BS_ECHO_DEBUG:-$BS_FALSE}

# Default sleep time used when waiting for daemons to start, restart and checking for these running
__DEFAULT_SLEEP=3

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#         NAME:  getram
#  DESCRIPTION:  Calculates ram for VM. Minimum 2 GiB / Max 8 GiB
#----------------------------------------------------------------------------------------------------------------------
getram()
{
  _VAGRANT_VM_RAM=`awk '/MemTotal/ { printf "%.3f \n", $2/1024/1024 }' /proc/meminfo`
  if [ ${_VAGRANT_VM_RAM%.*} -ge 15 ]; then
    _VAGRANT_VM_RAM=8192
  else
    _VAGRANT_VM_RAM=`expr ${_VAGRANT_VM_RAM%.*} / 2`
    rem=$(( $_VAGRANT_VM_RAM % 2 ))
    if [ $rem -gt 0 ]; then
      _VAGRANT_VM_RAM=`expr ${_VAGRANT_VM_RAM} - 1`
    fi
    if [ $_VAGRANT_VM_RAM -lt 2 ]; then _VAGRANT_VM_RAM=2; fi
    _VAGRANT_VM_RAM=`expr ${_VAGRANT_VM_RAM} \* 1024`
  fi
}

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#         NAME:  mk_vagrantfile
#  DESCRIPTION:  Write Vagrantfile.
#----------------------------------------------------------------------------------------------------------------------
mk_vagrantfile()
{
    cat > "${_VAGRANTFILE_DIR}/Vagrantfile" <<- EOM
# -*- mode: ruby -*-
# vi: set ft=ruby :

version = "2019.07.09-001"

private_network = "192.168.55"
vm_ip = 201
vm_hostnames = ["${_VAGRANT_VM_NAME}"]
vm_ram = $_VAGRANT_VM_RAM
vm_cpus = $_VAGRANT_VM_CORES
vm_vagbox = "${_VAGRANT_VM_BOX}"

Vagrant.configure("2") do |config|
  (0..vm_hostnames.length - 1).each do |i|
    config.vm.define vm_hostnames[i] do |mk|
      mk.vm.provider "virtualbox" do |vb|
        vb.memory = vm_ram
        vb.cpus = vm_cpus
      end
      mk.vm.box = vm_vagbox
      mk.vm.synced_folder '.', '/vagrant', SharedFoldersEnableSymlinksCreate: false
      mk.vm.network "private_network", ip: private_network + "." + (vm_ip + i).to_s
    end
  end
end
EOM
}

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#         NAME:  mk_bootstrap_script
#  DESCRIPTION:  Creates script to bootstrap the vagrant VM
#----------------------------------------------------------------------------------------------------------------------
mk_bootstrap_script()
{

    cat > "vagrant_bootstrap.sh" <<- EOM
#!/bin/sh -
if ! [ \$(id -u) -eq 0 ]; then
    echo "Must be root"
    exit 1
fi
cd /root
if [ -d /root/rmrmrr ]; then
    rm -rf rmrmrr
fi
mkdir rmrmrr
cd rmrmrr
echo "==== UPDATE OS ====================================="
apt update
DEBIAN_FRONTEND=noninteractive apt upgrade -y
echo "==== BUILD PKG LIST ====================================="
pkgs="build-essential"
pkgs="git \${pkgs}"
pkgs="patch \${pkgs}"
pkgs="fakeroot \${pkgs}"
pkgs="devscripts \${pkgs}"
pkgs="libncurses5-dev \${pkgs}"
pkgs="libssl-dev \${pkgs}"
pkgs="libdw-dev \${pkgs}"
pkgs="libnuma-dev \${pkgs}"
pkgs="libslang2-dev \${pkgs}"
pkgs="libiberty-dev \${pkgs}"
pkgs="sphinx-common \${pkgs}"
pkgs="python3-sphinx \${pkgs}"
pkgs="bc \${pkgs}"
pkgs="flex \${pkgs}"
pkgs="bison \${pkgs}"
pkgs="libelf-dev \${pkgs}"
pkgs="libgtk2.0-dev \${pkgs}"
pkgs="libperl-dev \${pkgs}"
pkgs="asciidoc \${pkgs}"
pkgs="xmlto \${pkgs}"
pkgs="gnupg \${pkgs}"
pkgs="gnupg2 \${pkgs}"
pkgs="rsync \${pkgs}"
pkgs="lintian \${pkgs}"
pkgs="debhelper \${pkgs}"
echo "==== BEGIN APT PACKAGE INSTALL ====================================="
DEBIAN_FRONTEND=noninteractive apt install -y \${pkgs}
echo "==== GET SOURCES ====================================="
git clone --depth=1 git://git.proxmox.com/git/mirror_ubuntu-disco-kernel.git
git clone --depth=1 git://git.proxmox.com/git/pve-kernel.git
mv mirror_ubuntu-disco-kernel ubuntu-disco
echo "==== CREATING PATCH FILE ============================================"
search="return -EPERM;"
targetfile="ubuntu-disco/drivers/iommu/intel-iommu.c"
if (cat "\${targetfile}" | grep "\${search}"); then
    sed "/\${search}/d" "\${targetfile}" > intel-iommu_new.c
fi
patchfile="pve-kernel/patches/kernel/9000-remove_rmrr_check.patch"
diff -u "\${targetfile}" intel-iommu_new.c > "\${patchfile}"
sed -i "s|--- \${targetfile}|--- a/drivers/iommu/intel-iommu.c|g" "\${patchfile}"
sed -i "s|+++ intel-iommu_new.c|+++ b/drivers/iommu/intel-iommu.c|g" "\${patchfile}"
sed -i "s/{KREL}-pve/{krel}-pve-rmrmrr/g" pve-kernel/Makefile
if [ -d submodules/ubuntu-disco ]; then
    cd submodules
    rm -rf ubuntu-disco
    cd ..
fi
ln -sr ../ubuntu-disco submodules/ubuntu-disco
echo "==== BOOTSTRAP COMPLETE ========================================="
exit 0
EOM
    if $_skip_vagrant; then
        mv vagrant_bootstrap.sh bootstrap.sh
    fi
}

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __detect_color_support
#   DESCRIPTION:  Try to detect color support.
#----------------------------------------------------------------------------------------------------------------------
__detect_color_support() {
    # shellcheck disable=SC2181
    _COLORS=`tput colors 2>/dev/null || echo 0`
    if [ $? -eq 0 ] && [ "$_COLORS" -gt 2 ]; then
        RC='\033[1;31m'
        GC='\033[1;32m'
        BC='\033[1;34m'
        YC='\033[1;33m'
        EC='\033[0m'
    else
        RC=""
        GC=""
        BC=""
        YC=""
        EC=""
    fi
}

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  echoerror
#   DESCRIPTION:  Echo errors to stderr.
#----------------------------------------------------------------------------------------------------------------------
echoerror() {
    printf "${RC} * ERROR${EC}: %s\\n" "$@" 1>&2;
    write_logfile "ERROR: $@"
}

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  echoinfo
#   DESCRIPTION:  Echo information to stdout.
#----------------------------------------------------------------------------------------------------------------------
echoinfo() {
    printf "${GC} *  INFO${EC}: %s\\n" "$@";
    write_logfile "INFO: $@"
}

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  echowarn
#   DESCRIPTION:  Echo warning information to stdout.
#----------------------------------------------------------------------------------------------------------------------
echowarn() {
    printf "${YC} *  WARN${EC}: %s\\n" "$@";
    write_logfile "WARN: $@"
}

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  echodebug
#   DESCRIPTION:  Echo debug information to stdout.
#----------------------------------------------------------------------------------------------------------------------
echodebug() {
    if [ "$_ECHO_DEBUG" -eq $BS_TRUE ]; then
        printf "${BC} * DEBUG${EC}: %s\\n" "$@";
    fi
    write_logfile "DEBUG: $@"
}

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __check_command_exists
#   DESCRIPTION:  Check if a command exists.
#----------------------------------------------------------------------------------------------------------------------
__check_command_exists() {
    command -v "$1" > /dev/null 2>&1
}

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  write_logfile
#   DESCRIPTION:  Writes to the logfile
#----------------------------------------------------------------------------------------------------------------------
write_logfile()
{
    if [ "$__LogFile" -eq $BS_TRUE ]; then
        echo "#[`date +"%Y%m%d %T"`] $@" >> "${_LOGFILE}"
    fi
}

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#         NAME:  realpath
#  DESCRIPTION:  Cross-platform realpath command. Because Mac.
#----------------------------------------------------------------------------------------------------------------------
realpath() {
    echo "`perl -e 'use Cwd "abs_path";print abs_path(shift)' "$1"`"
}

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#         NAME:  vagrant_box
#  DESCRIPTION:  Checks that the vagrant box we want is available and up to date.
#----------------------------------------------------------------------------------------------------------------------
vagrant_box()
{
    if ! (vagrant box list | grep "${_VAGRANT_VM_BOX}"); then
        if ! (vagrant box add "${_VAGRANT_VM_BOX}"); then
            echoerror "Unable to load vagrant box ${_VAGRANT_VM_BOX}. Cannot continue."
            exit 1
        fi
    else
        if ! (vagrant box update --box "${_VAGRANT_VM_BOX}"); then
            echowarn "Unable to update vagrant box ${_VAGRANT_VM_BOX}. Continuing without update..."
        fi
    fi
}

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#         NAME:  __usage
#  DESCRIPTION:  Display usage information.
#----------------------------------------------------------------------------------------------------------------------
__usage() {
        cat << EOT

          Usage :  ${__ScriptName} [options]

          Options:
            -x | --no-vagrant     Skip Vagrant usage

            
EOT
}

#----------------------------------------------------------------------------------------------------------------------
#  Handle command line arguments
#----------------------------------------------------------------------------------------------------------------------
_skip_vagrant=$BS_FALSE

_parsed=$(getopt --options=${_OPTIONS} --longoptions=${_LONGOPTIONS} --name "$0" -- "$@")
eval set -- "$_parsed"

while true; do
    case "$1" in
        -x|--no-vagrant)
            _skip_vagrant=$BS_TRUE
            shift
            ;;
        --)
            shift
            break
            ;;
        *)
            echo "Unable to parse command line options."
            exit 1
            ;;
    esac
done

#----------------------------------------------------------------------------------------------------------------------
#  DESCRIPTION:  Run sanity checks
#----------------------------------------------------------------------------------------------------------------------
#if ! [ $(id -u) -eq 0 ]; then
#    echoerror "must be run as root"
#fi
if ! [ __check_command_exists vagrant ] && ! [ $_skip_vagrant ]; then
    echo
    echoerror "vagrant missing. Install vagrant from https://vagrantup.com"
    echo
    exit 1
fi
if ! [ __check_command_exists virtualbox ] && ! [ $_skip_vagrant ]; then
    echo
    echoerror "virtualbox missing. Install virtualbox from https://www.virtualbox.com"
    echo
    exit 1
fi

#---  MAIN  -----------------------------------------------------------------------------------------------------------
#  DESCRIPTION:  Start main program
#----------------------------------------------------------------------------------------------------------------------
__detect_color_support
mk_bootstrap_script
if ! $_skip_vagrant; then
    getram
    echo "VM RAM: ${_VAGRANT_VM_RAM}"
    echo "VM CPU: ${_VAGRANT_VM_CORES}"
    vagrant_box
    mk_vagrantfile
    vagrant up || ( echoerror "vagrant up failed" && exit 1 )
    vcmd="sudo sh /vagrant/vagrant_bootstrap.sh"
    echo "Vagrant Bootstrap Command: ${vcmd}"
    vagrant ssh "${_VAGRANT_VM_NAME}" -- -q -t "${vcmd}" || echo "Vagrant command failed"
else
    echo "Created bootstrap script. As root, run: sh bootstrap.sh"
    echo ""
fi
# TODO: bootstrap script should return user to original directory when finished
# TODO: script should clean up after itself? 
# TODO: perhaps add a cleanup command line option
