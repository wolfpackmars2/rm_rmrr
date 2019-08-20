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
pkgs="bc"
pkgs="${pkgs} bison"
pkgs="${pkgs} dh-python"
pkgs="${pkgs} flex"
pkgs="${pkgs} libdw-dev"
pkgs="${pkgs} libiberty-dev"
pkgs="${pkgs} libnuma-dev"
pkgs="${pkgs} libslang2-dev"
pkgs="${pkgs} libssl-dev"
pkgs="${pkgs} lintian"
pkgs="${pkgs} rsync"
pkgs="${pkgs} sphinx-common"
echo "==== BEGIN APT PACKAGE INSTALL ====================================="
DEBIAN_FRONTEND=noninteractive apt install -y ${pkgs}
echo "==== GET SOURCES ====================================="
cd "${gitdir}"
git clone --depth=1 git://git.proxmox.com/git/pve-kernel.git
cd pve-kernel/submodules || exit 2
rm -rf ubuntu-disco
git clone --depth=1 git://git.proxmox.com/git/mirror_ubuntu-disco-kernel ubuntu-disco
rm -rf zfsonlinux
git clone --depth=1 git://git.proxmox.com/git/zfsonlinux
cd zfsonlinux || exit 3
rm -rf upstream
git clone --depth=1 git://git.proxmox.com/git/mirror_zfs upstream
cd upstream/scripts || exit 4
rm -rf zfs-images
git clone --depth=1 https://github.com/zfsonlinux/zfs-images
cd "${gitdir}"
echo "==== CREATING PATCH FILE ============================================"
search="return -EPERM;"
targetfile="pve-kernel/submodules/ubuntu-disco/drivers/iommu/intel-iommu.c"
if (grep "${search}" "${targetfile}"); then
        sed "/${search}/d" "${targetfile}" > intel-iommu_new.c
fi
patchfile="pve-kernel/patches/kernel/9000-fix_rmrr.patch"
diff -u "${targetfile}" intel-iommu_new.c > "${patchfile}"
sed -i "s|--- ${targetfile}|--- a/drivers/iommu/intel-iommu.c|g" "${patchfile}"
sed -i "s|+++ intel-iommu_new.c|+++ b/drivers/iommu/intel-iommu.c|g" "${patchfile}"
sed -i "s/{KREL}-pve/{krel}-pve-rmrmrr/g" pve-kernel/Makefile
rm intel-iommu_new.c
echo "cd into ${gitdir}/pve-kernel and run make -j"
echo "==== BOOTSTRAP COMPLETE ========================================="
exit 0
