#!/bin/sh -
#======================================================================================================================
# vim: softtabstop=4 shiftwidth=4 expandtab fenc=utf-8 spelllang=en cc=120
#======================================================================================================================
#
#          FILE: test.sh
#
#   DESCRIPTION: Test file script
#
#          BUGS: github.com/wolfpackmars2
#
#     COPYRIGHT: (c) 2019 S. Groesz
#
#  ORGANIZATION: GROESZ
#       CREATED: 2019.07.31
#======================================================================================================================
set -o nounset                              # Treat unset variables as an error

__VERSION="2019.08.07-0"
__TEMPLATE_VERSION="0"

__ScriptName="${0##*/}"
__ScriptFullName="$0"
__ScriptArgs="$*"
__BaseDir=$(pwd)

# Bootstrap script truth values
BS_TRUE=1
BS_FALSE=0

_ECHO_DEBUG=${BS_ECHO_DEBUG:-$BS_FALSE}

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __detect_color_support
#   DESCRIPTION:  Try to detect color support.
#----------------------------------------------------------------------------------------------------------------------
__detect_color_support() {
    _COLORS=${BS_COLORS:-$(tput colors 2>/dev/null || echo 0)}
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
#         NAME:  write_bootstrap_scripts
#  DESCRIPTION:  Create the scripts used in the VM.
#----------------------------------------------------------------------------------------------------------------------
write_bootstrap_scripts() {
    cat > "${_lax_shared_dir}/setup.sh" <<- EOM
#!/bin/sh -
if ! [ "\$(id -u)" -eq 0 ]; then
    echo "Must be root"
    exit 1
fi
workdir="/root/work"
startdir=\$(pwd -P)
if ! [ -d "\${workdir}" ]; then
    echo "bootstrap files missing"
    exit 1
fi
basedir=\$(cat "\${workdir}/basedir._")
shareddir=\$(cat "\${workdir}/shareddir._"
if ! [ -f "\${workdir}/gitdir._" ]; then
    echo "\${workdir}/git" > "\${workdir}/gitdir._"
fi
if ! [ -d "\${shareddir}" ]; then
    echo "Shared directory \${shareddir} not available. Cannot continue."
    exit 1
fi
gitdir=\$(cat "\${workdir}/gitdir._")
BS_FALSE=$BS_FALSE
BS_TRUE=$BS_TRUE
TemplateUpdate=\$BS_FALSE
# Check locale
if (locale 2>&1 | grep "locale: Cannot set"); then
    echo "Locales are broken"
    echo "en_US.UTF-8 UTF-8" >> /etc/locale.gen
    locale-gen
    update-locale LANG=en_US.UTF-8 UTF-8
    dpkg-reconfigure --frontend=noninteractive locales
    TemplateUpdate=\$BS_TRUE
    echo "Locales fixed. Template update required."
fi
# Check lsbrelease
if ! (command -v "lsb_release" > /dev/null 2>&1); then
    apt update
    DEBIAN_FRONTEND=noninteractive apt install lsb-release -y
    TemplateUpdate=\$BS_TRUE
fi
release=\$(lsb_release -cs)
# Check repos
if ! [ -e "/etc/apt/sources.list.d/pve-install-repo.list" ]; then
    case \$release in
        buster)
            gpg_key="proxmox-ve-release-6.x.gpg"
            pve_repo="deb http://download.proxmox.com/debian/pve buster pve-no-subscription"
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
    # wget "http://download.proxmox.com/debian/\${gpg_key}" -O "/etc/apt/trusted.gpg.d/\${gpg_key}"
    wget -O- "http://download.proxmox.com/debian/\${gpg_key}" | apt-key add -
    echo "\${pve_repo}" > /etc/apt/sources.list.d/pve-install-repo.list
fi
# Check for updates
apt-get update > /dev/null 2>&1 || (echo "Something went wrong downloading package lists" && exit 1)
# updates=\$(apt-get dist-upgrade -s | grep 'upgraded,')
# if [ "\$(echo \$updates | cut -d ' ' -f 1)" -ne 0 ]; then _upgrade=\$BS_TRUE; fi
# if [ "\$(echo \$updates | cut -d ' ' -f 3)" -ne 0 ]; then _upgrade=\$BS_TRUE; fi
# if [ "\$(echo \$updates | cut -d ' ' -f 6)" -ne 0 ]; then _upgrade=\$BS_TRUE; fi
# if [ "\$(echo \$updates | cut -d ' ' -f 10)" -ne 0 ]; then _upgrade=\$BS_TRUE; fi
pkgs="build-essential"
pkgs="\$pkgs patch"
pkgs="\$pkgs fakeroot"
pkgs="\$pkgs debhelper"
pkgs="\$pkgs libpve-common-perl"
pkgs="\$pkgs pve-doc-generator"
pkgs="\$pkgs git"
start=\$(date +%s)
DEBIAN_FRONTEND=noninteractive apt-get dist-upgrade -y
# Install base packages
DEBIAN_FRONTEND=noninteractive apt-get install -y \${pkgs}
end=\$(date +%s)
duration=\$((end-start))
if [ \$duration -gt 120 ]; then TemplateUpdate=\$BS_TRUE; fi
# git code
if [ -d "\${gitdir}" ]; then
    mkdir -p "\${gitdir}"
fi
cd "\${gitdir}"
# if ! [ -d "pve-common" ]; then
#     git clone --depth=1 git://git.proxmox.com/git/pve-common.git
# fi
# Install build packages
# TODO
cd "\${startdir}"
EOM

    cat > "${_lxc_shared_dir}/basic.sh" <<- EOM
#!/bin/sh -
if ! [ "\$(id -u)" -eq 0 ]; then
    echo "Must be root"
    exit 1
fi
basedir="/root"
shareddir="/root/shared"
workdir="/root/work"
if ! [ -d "\${workdir}" ]; then (mkdir -p "\${workdir}"); fi
echo "\${basedir}" > "\${workdir}/basedir._"
echo "\${shareddir}" > "\${workdir}/shareddir._"
EOM

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#         NAME:  realpath
#  DESCRIPTION:  Cross-platform realpath command. Because Mac.
#----------------------------------------------------------------------------------------------------------------------
realpath() {
    perl -e 'use Cwd "abs_path";print abs_path(shift)' "$1"
}

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#         NAME:  update_local_template
#  DESCRIPTION:  Retrieves most current template
#----------------------------------------------------------------------------------------------------------------------
update_local_template() {
    echodebug "f: update_local_template"    
    pveam update || ( echoerror "unable to download template list" && exit 1 )
    _avail_tmpl=$(pveam available | grep system | grep "${_tmpl}" | head -1 | sed -n -e 's/^system//p' | xargs)
    _local_tmpl=$(pveam list local | grep "${_tmpl}" | tail -1 | cut -d " " -f 1)
    __local_tmpl=$(echo ${_local_tmpl} | sed -n -e 's/^.*\///p')
    if ! [ "${_avail_tmpl}" = "${__local_tmpl}" ]; then
        # download updated template
        echoinfo "Download latest ${_tmpl} template"
        pveam download local $_avail_tmpl || ( echoerror "error downloading template"; exit 1 )
        _local_tmpl=$(pveam list local | grep "${_tmpl}" | tail -1 | cut -d " " -f 1)
    fi
    echodebug "_avail_tmpl: ${_avail_tmpl}"
    echodebug "_local_tmpl: ${_local_tmpl}"
    echodebug "__local_tmpl: ${__local_tmpl}"
    echodebug "fend: update_local_template"
}

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#         NAME:  create_lxc
#  DESCRIPTION:  Creates an LXC instance
#----------------------------------------------------------------------------------------------------------------------
create_lxc() {
    echodebug "f: create_lxc"    
    pct create $_LXC_ID "$_local_tmpl" -storage $_storage -memory $_lxc_mem \
        -net0 "name=eth0,bridge=vmbr${_vmbr},hwaddr=FA:4D:70:91:B8:6F,ip=dhcp,type=veth" \
        -hostname buildr -cores $_cores -rootfs 80 \
        -mp0 "${_lxc_shared_dir},mp=/root/shared,ro=${BS_FALSE}" || ( echoerror \
        "failed to create container" && exit 1 )
    echoinfo "Created LXC ${_LXC_ID}"
    echodebug "fend: create_lxc"
}

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#         NAME:  __usage
#  DESCRIPTION:  Display usage information
#----------------------------------------------------------------------------------------------------------------------
__usage() {
    cat << EOT
  Usage : ${__ScriptName} [options]

  Options:
    -b <id>           Specify Bridge to connect to. Default 0 (vmbr0)
    -i <id>           Specify the LXC id to use. Default 500.
    -k                Keep existing LXC. Default is to replace existing LXC.
    -c                Create clean working directory "$(pwd)/shared"
    -C <#>            LXC Core Count. Default (#corecount - 4)
    -R <#>            LXC Ram (in GB). Default 4
    -V                Print Version Information
    -v                Show debugging information
    -S <share_path>   Set path to shared directory


EOT
}

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#         NAME:  __print_header
#  DESCRIPTION:  Display usage information
#----------------------------------------------------------------------------------------------------------------------
__print_header() {
    echoinfo "Script Version: $__VERSION"
    echoinfo "Template Version: $__TEMPLATE_VERSION"
    echoinfo "--------------------------------------"
}
#----------------------------------------------------------------------------------------------------------------------
#  DESCRIPTION:  Run sanity checks
#----------------------------------------------------------------------------------------------------------------------
__detect_color_support
[ "$(id -u)" -eq 0 ] || (echoerror "This script must be run as root" && exit 1)

#----------------------------------------------------------------------------------------------------------------------
#  DESCRIPTION:  Handle command line args
#----------------------------------------------------------------------------------------------------------------------
_clean=${CLEAN:-$BS_FALSE}
_tmpl=${TMPL:-"debian-10"}
_mod_tmpl=${MOD_TMPL:-"rmrmrr-${__TEMPLATE_VERSION}-${_tmpl}"}
_LXC_ID=${LXC_ID:-500}
_cores=${CORES:-$(($(grep -c ^processor /proc/cpuinfo) - 4))}
_vmbr=${VMBR:-0}
_clean_lxc=${CLEAN_LXC:-$BS_TRUE}
_lxc_mem=${MEM:-$(expr 1024 \* 4)}
_storage=${STORAGE:-"local-lvm"}
__ScriptFullName=$(realpath $0)
__ScriptDirectory="${__ScriptFullName%/*}"
_lxc_shared_dir=${SHARED:-"${__ScriptDirectory}/shared"}

_OPTIONS="b:i:kcC:R:S:vVh"
_LONGOPTIONS="help"
_parsed=$(getopt --options=${_OPTIONS} --longoptions=${_LONGOPTIONS} --name "$0" -- "$@")
eval set -- "$_parsed"

while true; do
    case "$1" in
        -k)
            _clean_lxc=$BS_FALSE
            shift
            ;;
        -h)
            __usage
            exit 0
            ;;
        -S)
            shift
            _lxc_shared_dir=$(realpath "$1")
            shift
            ;;
        -v)
            _ECHO_DEBUG=$BS_TRUE
            shift
            ;;
        -V)
            __print_header
            exit 0
            ;;
        -R)
            shift
            _lxc_mem=$(expr 1024 \* $1)
            shift
            ;;
        -c)
            _clean=$BS_TRUE
            shift
            ;;
        -i)
            shift
            _LXC_ID=$1
            shift
            ;;
        -C)
            shift
            _cores=$1
            shift
            ;;
        -b)
            shift
            _vmbr=$1
            shift
            ;;
        --)
            shift
            break
            ;;
        *)
            echoerror "Unable to parse command line options."
            exit 1
            ;;
    esac
done

#---  DEBUG  ----------------------------------------------------------------------------------------------------------
#  DESCRIPTION:  Output variable values for debugging
#----------------------------------------------------------------------------------------------------------------------
echodebug "_clean: $_clean"
echodebug "_tmpl: $_tmpl"
echodebug "_mod_tmpl: $_mod_tmpl"
echodebug "_LXC_ID: $_LXC_ID"
echodebug "_cores: $_cores"
echodebug "_vmbr: $_vmbr"
echodebug "_clean_lxc: $_clean_lxc"
echodebug "_lxc_mem: $_lxc_mem"
echodebug "_lxc_shared_dir: $_lxc_shared_dir"
echodebug "_storage: $_storage"
echodebug "__ScriptName: $__ScriptName"
echodebug "__ScriptFullName: $__ScriptFullName"
echodebug "__ScriptDirectory: $__ScriptDirectory"

#---  MAIN  -----------------------------------------------------------------------------------------------------------
#  DESCRIPTION:  Start main program
#----------------------------------------------------------------------------------------------------------------------
__print_header
_local_tmpl=$(pveam list local | grep "${_mod_tmpl}" | cut -d " " -f 1 )
if [ "${_local_tmpl}" = "" ]; then
    echoinfo "No RMRMRR template"
    update_local_template
fi
if [ -d "${_lxc_shared_dir}" ]; then
    if [ $_clean ]; then
        rm -rf "${_lxc_shared_dir}"
        mkdir -p "${_lxc_shared_dir}"
        echoinfo "replaced existing ${_lxc_shared_dir} directory"
    else
        echoinfo "using existing ${_lxc_shared_dir} directory"
    fi
else
    mkdir shared
    echoinfo "created new ${_lxc_shared_dir} directory"
fi
chmod o+rw shared
if (pct status $_LXC_ID); then
    echodebug "LXC ${_LXC_ID} exists"
    pct stop $_LXC_ID
    if [ $_clean_lxc ]; then
        pct destroy $_LXC_ID || (echoerror "Unable to destroy existing LXC ${_LXC_ID}" && exit 1)
        echodebug "Destroyed existing LXC ${_LXC_ID}"
        create_lxc
    fi
else
    create_lxc
fi
pct start $_LXC_ID || (echoerror "Failed to start LXC ${_LXC_ID}" && exit 1)
