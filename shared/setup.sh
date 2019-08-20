#!/bin/sh -
if ! [ "$(id -u)" -eq 0 ]; then
    echo "Must be root"
    exit 1
fi
workdir="/root/work"
logfile=$(cat "${workdir}/logfile._")
startdir=$(pwd -P)
if ! [ -d "${workdir}" ]; then
    echo "bootstrap files missing"
    exit 1
fi
basedir=$(cat "${workdir}/basedir._")
shareddir=$(cat "${workdir}/shareddir._")
if ! [ -f "${workdir}/gitdir._" ]; then
    echo "${workdir}/git" > "${workdir}/gitdir._"
fi
if ! [ -d "${shareddir}" ]; then
    echo "Shared directory ${shareddir} not available. Cannot continue."
    exit 1
fi
gitdir=$(cat "${workdir}/gitdir._")
BS_FALSE=0
BS_TRUE=1
TemplateUpdate=$BS_FALSE
# Check locale
if (locale 2>&1 | grep "locale: Cannot set"); then
    echo "Locales are broken"
    echo "en_US.UTF-8 UTF-8" >> /etc/locale.gen
    locale-gen
    update-locale LANG=en_US.UTF-8 UTF-8
    dpkg-reconfigure --frontend=noninteractive locales
    TemplateUpdate=$BS_TRUE
    echo "Locales fixed. Template update required."
fi
# Check lsbrelease
if ! (command -v "lsb_release" > /dev/null 2>&1); then
    apt update
    DEBIAN_FRONTEND=noninteractive apt install lsb-release -y
    TemplateUpdate=$BS_TRUE
fi
release=$(lsb_release -cs)
# Check repos
if ! [ -e "/etc/apt/sources.list.d/pve-install-repo.list" ]; then
    case $release in
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
    wget "http://download.proxmox.com/debian/${gpg_key}" -O "/etc/apt/trusted.gpg.d/${gpg_key}"
    # wget -O- "http://download.proxmox.com/debian/${gpg_key}" | apt-key add -
    echo "${pve_repo}" > /etc/apt/sources.list.d/pve-install-repo.list
fi
# Check for updates
apt-get update > /dev/null 2>&1 || (echo "Something went wrong downloading package lists" && exit 1)
# updates=$(apt-get dist-upgrade -s | grep 'upgraded,')
# if [ "$(echo $updates | cut -d ' ' -f 1)" -ne 0 ]; then _upgrade=$BS_TRUE; fi
# if [ "$(echo $updates | cut -d ' ' -f 3)" -ne 0 ]; then _upgrade=$BS_TRUE; fi
# if [ "$(echo $updates | cut -d ' ' -f 6)" -ne 0 ]; then _upgrade=$BS_TRUE; fi
# if [ "$(echo $updates | cut -d ' ' -f 10)" -ne 0 ]; then _upgrade=$BS_TRUE; fi
pkgs="build-essential"
pkgs="$pkgs patch"
pkgs="$pkgs fakeroot"
pkgs="$pkgs debhelper"
pkgs="$pkgs libpve-common-perl"
pkgs="$pkgs pve-kernel-5.0"
pkgs="$pkgs pve-doc-generator"
pkgs="$pkgs git"
start=$(date +%s)
DEBIAN_FRONTEND=noninteractive apt-get dist-upgrade -y
# Install base packages
DEBIAN_FRONTEND=noninteractive apt-get install -y ${pkgs}
end=$(date +%s)
duration=$((end-start))
if [ $duration -gt 120 ]; then TemplateUpdate=$BS_TRUE; fi
# git code
if ! [ -d "${gitdir}" ]; then
    mkdir -p "${gitdir}"
fi
cd "${gitdir}"
# if ! [ -d "pve-common" ]; then
#     git clone --depth=1 git://git.proxmox.com/git/pve-common.git
# fi
# Install build packages
# TODO
cd "${startdir}"
