#!/bin/sh -
#======================================================================================================================
# vim: softtabstop=4 shiftwidth=4 expandtab fenc=utf-8 spell spelllang=en cc=120
#======================================================================================================================
#
#          FILE: rm_rmrr.sh
#
#   DESCRIPTION: Create RMRR patch for latest PVE (Proxmox) kernel
#                Min Requirements: CPU Cores >= 4; 4GiB RAM
#                Rec Requirements: Quad Core CPU with HT or better; 16GiB RAM or greater
#                OS: Proxmox 
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
__Version="2019.07.30"

_OPTIONS="xifc"
_LONGOPTIONS="no-vagrant"
CORES=$(grep -c ^processor /proc/cpuinfo)
CORES=$((CORES - 4))
if [ "${CORES}" -lt 1 ]; then
    CORES=1
fi
VM_NAME="RMRMRR"
_LXC_ID=500
_CONTAINER_TEMPLATE="local:vztmpl/debian-10.0-standard_10.0-1_amd64.tar.gz"
_VAGRANTFILE_DIR=$(pwd)

# Bootstrap script truth values
BS_TRUE=1
BS_FALSE=0

_ECHO_DEBUG=${BS_ECHO_DEBUG:-$BS_FALSE}

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#         NAME:  getram
#  DESCRIPTION:  Calculates ram for VM. Minimum 2 GiB / Max 8 GiB
#----------------------------------------------------------------------------------------------------------------------
getram()
{
  VM_MEM=$(awk '/MemTotal/ { printf "%.3f \n", $2/1024/1024 }' /proc/meminfo)
  if [ "${VM_MEM%.*}" -ge 15 ]; then
    VM_MEM=8192
  else
    VM_MEM=$((${VM_MEM%.*} / 2))
    rem=$(( VM_MEM % 2 ))
    if [ $rem -gt 0 ]; then
      VM_MEM=$((VM_MEM - 1))
    fi
    if [ $VM_MEM -lt 2 ]; then VM_MEM=2; fi
    VM_MEM=$((VM_MEM * 1024))
  fi
}

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#         NAME:  mk_bootstrap_script
#  DESCRIPTION:  Creates script to bootstrap the vagrant VM
#----------------------------------------------------------------------------------------------------------------------
mk_bootstrap_script()
{

    cat > "buildr/bootstrap.sh" <<- EOM
#!/bin/sh -
if ! [ "\$(id -u)" -eq 0 ]; then
    echo "Must be root"
    exit 1
fi
basedir=\$(pwd)
if [ -d rmrmrr ]; then
    rm -rf rmrmrr
fi
mkdir rmrmrr
cd rmrmrr || exit 1
echo "==== UPDATE OS ====================================="
chk_locale()
{
    if (locale 2>&1 | grep "locale: Cannot set"); then
        # locales are broken
        if [ "\$once" -eq 1 ]; then exit 1; fi
        echo "en_US.UTF-8 UTF-8" >> /etc/locale.gen 
        locale-gen
        update-locale LANG=en_US.UTF-8 UTF-8
        dpkg-reconfigure --frontend=noninteractive locales
        once=1
    else
        once=0
    fi
}
chk_locale
if [ \$once -eq 1 ]; then chk_locale; fi
if [ \$once -eq 1 ]; then (echo "Unable to set locale." && exit 1); fi
chk_lsbrelease()
{
    if ! (command -v "lsb_release" > /dev/null 2>&1); then
        if [ \$once -eq 1 ]; then exit 1; fi
        apt update
        DEBIAN_FRONTEND=noninteractive apt install lsb-release -y
        once=1
    else
        once=0
    fi
}
chk_lsbrelease
if [ \$once -eq 1 ]; then chk_lsbrelease; fi
if [ \$once -eq 1 ]; then (echo "Unable to install lsb_release" && exit 1); fi
release=\$(lsb_release -cs)
case \$release in
    buster)
        gpg_key="proxmox-ve-release-6.x.gpg"
        pve_repo="deb http://download.proxmox.com/debian/pve buster pvetest"
        ;;
    stretch)
        gpg_key="proxmox-ve-release-5.x.gpg"
        pve_repo="deb http://download.proxmox.com/debian/pve stretch pve-no-subscription"
        ;;
    *)
        echo "Unsupported OS"
        exit 1
        ;;
esac
wget "http://download.proxmox.com/debian/\${gpg_key}" -O "/etc/apt/trusted.gpg.d/\${gpg_key}"
echo "\${pve_repo}" > /etc/apt/sources.list.d/pve-install-repo.list
apt update
DEBIAN_FRONTEND=noninteractive apt dist-upgrade -y
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
pkgs="dh-python \${pkgs}"
pkgs="libpve-common-perl \${pkgs}"
echo "==== BEGIN APT PACKAGE INSTALL ====================================="
DEBIAN_FRONTEND=noninteractive apt install -y \${pkgs}
echo "==== GET SOURCES ====================================="
# TODO: add support for building for Proxmox 5
git clone --depth=1 git://git.proxmox.com/git/pve-kernel.git
cd pve-kernel/submodules || exit 2
rm -rf ubuntu-disco
git clone --depth=1 git://git.proxmox.com/git/mirror_ubuntu-disco-kernel
mv mirror_ubuntu-disco-kernel ubuntu-disco
rm -rf zfsonlinux
git clone --depth=1 git://git.proxmox.com/git/zfsonlinux
cd zfsonlinux || exit 3
git clone --depth=1 git://git.proxmox.com/git/mirror_zfs
rm -rf upstream
mv mirror_zfs upstream
cd upstream/scripts || exit 4
rm -rf zfs-images
git clone --depth=1 https://github.com/zfsonlinux/zfs-images
cd "\${basedir}/rmrmrr" || exit 5
echo "==== CREATING PATCH FILE ============================================"
search="return -EPERM;"
targetfile="pve-kernel/submodules/ubuntu-disco/drivers/iommu/intel-iommu.c"
if (grep "\${search}" "\${targetfile}"); then
    sed "/\${search}/d" "\${targetfile}" > intel-iommu_new.c
fi
patchfile="pve-kernel/patches/kernel/9000-remove_rmrr_check.patch"
diff -u "\${targetfile}" intel-iommu_new.c > "\${patchfile}"
sed -i "s|--- \${targetfile}|--- a/drivers/iommu/intel-iommu.c|g" "\${patchfile}"
sed -i "s|+++ intel-iommu_new.c|+++ b/drivers/iommu/intel-iommu.c|g" "\${patchfile}"
sed -i "s/{KREL}-pve/{krel}-pve-rmrmrr/g" pve-kernel/Makefile
rm intel-iommu_new.c
echo "cd into /root/rmrmrr/pve-kernel and run make -j"
echo "==== BOOTSTRAP COMPLETE ========================================="
exit 0
EOM
}

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __detect_color_support
#   DESCRIPTION:  Try to detect color support.
#----------------------------------------------------------------------------------------------------------------------
__detect_color_support() {
    _COLORS=$(tput colors 2>/dev/null || echo 0)
    # shellcheck disable=SC2181
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
}

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  echoinfo
#   DESCRIPTION:  Echo information to stdout.
#----------------------------------------------------------------------------------------------------------------------
echoinfo() {
    printf "${GC} *  INFO${EC}: %s\\n" "$@";
}

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  echowarn
#   DESCRIPTION:  Echo warning information to stdout.
#----------------------------------------------------------------------------------------------------------------------
echowarn() {
    printf "${YC} *  WARN${EC}: %s\\n" "$@";
}

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  echodebug
#   DESCRIPTION:  Echo debug information to stdout.
#----------------------------------------------------------------------------------------------------------------------
echodebug() {
    if [ "$_ECHO_DEBUG" -eq $BS_TRUE ]; then
        printf "${BC} * DEBUG${EC}: %s\\n" "$@";
    fi
}

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __check_command_exists
#   DESCRIPTION:  Check if a command exists.
#----------------------------------------------------------------------------------------------------------------------
__check_command_exists() {
    command -v "$1" > /dev/null 2>&1
}

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#         NAME:  realpath
#  DESCRIPTION:  Cross-platform realpath command. Because Mac.
#----------------------------------------------------------------------------------------------------------------------
realpath() {
    perl -e 'use Cwd "abs_path";print abs_path(shift)' "$1"
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
                                  This will create the bootstrap
                                  script then exit.
            -i <id>               Specify Virtual Machine ID. Default 500.
            -f                    Force overwrite existing VM <id>
            -c                    Create working directory. Overwrite if exists.



EOT
}

#----------------------------------------------------------------------------------------------------------------------
#  Handle command line arguments
#----------------------------------------------------------------------------------------------------------------------
_skip_vm=$BS_FALSE
force_override=$BS_FALSE
_make_workdir=$BS_FALSE

_parsed=$(getopt --options=${_OPTIONS} --longoptions=${_LONGOPTIONS} --name "$0" -- "$@")
eval set -- "$_parsed"

while true; do
    case "$1" in
        -x|--no-vagrant)
            _skip_vm=$BS_TRUE
            shift
            ;;
        -i)
            shift
            _LXC_ID=$1
            shift
            ;;
        -f)
            force_override=$BS_TRUE
            shift
            ;;
        -c)
            _make_workdir=$BS_TRUE
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
__detect_color_support
if ! (__check_command_exists pct) && [ $_skip_vm -eq $BS_FALSE ]; then
    echo
    echoerror "Proxmox 'pct' command missing. Install proxmox."
    echo
    exit 1
fi
if ! (__check_command_exists pvesm) && [ $_skip_vm -eq $BS_FALSE ]; then
    echo
    echoerror "Proxmox 'pvesm' command missing. Install proxmox."
    echo
    exit 1
fi

#---  MAIN  -----------------------------------------------------------------------------------------------------------
#  DESCRIPTION:  Start main program
#----------------------------------------------------------------------------------------------------------------------
mk_bootstrap_script
if [ "$_skip_vm" -eq $BS_FALSE ]; then
    getram
    echo "VM RAM: ${VM_MEM}"
    echo "VM CPU: ${CORES}"
    if [ -d buildr ] && [ $_make_workdir ]; then
        echo "$(pwd)/buildr exists. Using existing directory. Use option -c to override this behavior."
    else
        if [ -d buildr ]; then
            rm -rf buildr
        fi
        mkdir buildr
    fi
    chmod o+rw buildr
    if (pct status $_LXC_ID) && [ $force_override -eq $BS_TRUE ]; then
        pct destroy $_LXC_ID || ( pct stop $_LXC_ID && pct destroy $_LXC_ID ) || echoerror "Unable to destroy LXC $_LXC_ID"
    fi
    if (pct status $_LXC_ID); then
        echo "VM ID ${_LXC_ID} exists. Specify a different ID with the -i option or override with option -f."
        exit 1
    fi
    pct create $_LXC_ID "${_CONTAINER_TEMPLATE}" \
        -storage local-lvm -memory 4096 \
        -net0 name=eth0,bridge=vmbr0,hwaddr=FA:4D:70:91:B8:6F,ip=dhcp,type=veth \
        -hostname buildr -cores $CORES -rootfs 80 \
        -mp0 "$(pwd)/buildr,mp=/root/buildr,ro=$BS_FALSE" || ( echoerror \
        "failed to create container" && exit 1 )
    pct start $_LXC_ID || ( echoerror "failed to start container ${_LXC_ID}" && exit 1 )
    vcmd="sudo sh /vagrant/vagrant_bootstrap.sh"
    echo "Vagrant Bootstrap Command: ${vcmd}"
    #vagrant ssh "${VM_NAME}" -- -q -t "${vcmd}" || echo "Vagrant command failed"
    #TODO create and run build script
else
    echo "Created bootstrap script. As root, run: sh bootstrap.sh"
    echo ""
fi
# TODO: script should clean up after itself? 
# TODO: perhaps add a cleanup command line option
