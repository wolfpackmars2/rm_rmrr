#!/bin/sh -
search="return -EPERM;"
targetfile="/root/sshshare/rm_rmrr/shared/git/pve-kernel/submodules/ubuntu-disco/drivers/iommu/intel-iommu.c"
echo "targetfile: $targetfile"
if (grep "${search}" "${targetfile}"); then
        sed "/${search}/d" "${targetfile}" > /tmp/intel-iommu_new.c
fi
patchfile="/root/sshshare/rm_rmrr/shared/git/pve-kernel/patches/kernel/9000-fix_rmrr.patch"
diff -u "${targetfile}" /tmp/intel-iommu_new.c > "${patchfile}"
sed -i "s|--- ${targetfile}|--- a/drivers/iommu/intel-iommu.c|g" "${patchfile}"
sed -i "s|+++ /tmp/intel-iommu_new.c|+++ b/drivers/iommu/intel-iommu.c|g" "${patchfile}"
# sed -i "s/{KREL}-pve/{krel}-pve-rmrmrr/g" /root/sshshare/rm_rmrr/shared/git/pve-kernel/Makefile
rm /tmp/intel-iommu_new.c
echo "cd into /root/share/git/pve-kernel and run make -j"
echo "==== BOOTSTRAP COMPLETE ========================================="
exit 0

