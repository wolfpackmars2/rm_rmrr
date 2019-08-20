#!/bin/sh -
#setup proxmox repo
#setup proxmox
#download ISOs
#custom kernel
#100 OPNSense
#101 Nassrv
#10x SaltMaster
#x0x gitlab

# Bootstrap script truth values
BS_TRUE=1
BS_FALSE=0
_REBOOT=$BS_FALSE
_UPDATEIRFS=$BS_FALSE

# setup proxmox repo
if [ -e /etc/apt/sources.list.d/pve-enterprise.list ]; then
    if (grep -q enterprise /etc/apt/sources.list.d/pve-enterprise.list); then
        sed "s/enterprise.p/download.p/g" \
        /etc/apt/sources.list.d/pve-enterprise.list | sed \
        "s/pve-enterprise/pve-no-subscription/g" | sed \
        "s/https/http/g" > /etc/apt/sources.list.d/pve-no-subscription.list
    fi
    rm /etc/apt/sources.list.d/pve-enterprise.list
    apt update
fi

#setup network adapters
if ! (grep -q "#AUX1 vLAN" /etc/network/interfaces); then
    cat > /etc/network/interfaces <<- EOM
# network interface settings; autogenerated
# Please do NOT modify this file directly, unless you know what
# you're doing.
#
# If you want to manage parts of the network configuration manually,
# please utilize the 'source' or 'source-directory' directives to do
# so.
# PVE will preserve these directives, but will NOT read its network
# configuration from sourced files, so do not attempt to move any of
# the PVE managed interfaces into external files!

auto lo
iface lo inet loopback

iface enp4s0f0 inet manual

iface enp4s0f1 inet manual

iface enp4s0f2 inet manual

iface enp4s0f3 inet manual

auto vmbr0
iface vmbr0 inet static
    address  192.168.0.60
    netmask  24
    gateway  192.168.0.1
    bridge-ports enp4s0f0
    bridge-stp off
    bridge-fd 0
#LAN (black)

auto vmbr1
iface vmbr1 inet manual
    bridge-ports enp4s0f1
    bridge-stp off
    bridge-fd 0
#WAN (blue)

auto vmbr2
iface vmbr2 inet manual
    bridge-ports enp4s0f2
    bridge-stp off
    bridge-fd 0
#OPNSense LAN (white)

auto vmbr3
iface vmbr3 inet manual
    bridge-ports enp4s0f3
    bridge-stp off
    bridge-fd 0
#OPNSense HA (orange)

auto vmbr4
iface vmbr4 inet manual
    bridge-ports none
    bridge-stp off
    bridge-fd 0
#PVE vLAN

auto vmbr5
iface vmbr5 inet manual
    bridge-ports none
    bridge-stp off
    bridge-fd 0
#AUX0 vLAN

auto vmbr6
iface vmbr6 inet manual
    bridge-ports none
    bridge-stp off
    bridge-fd 0
#AUX1 vLAN
EOM
    systemctl restart networking
    echo "Updated Network Interfaces"
fi


# configure hardware passthrough
source="/etc/default/grub"
find="GRUB_CMDLINE_LINUX_DEFAULT=\"quiet\""
replace="GRUB_CMDLINE_LINUX_DEFAULT=\"quiet iommu=pt intel_iommu=on\""
#replace="GRUB_CMDLINE_LINUX_DEFAULT=\"quiet "
#replace="${replace}modprobe.blacklist=amdgpu"
#sed "s/GRUB_CMDLINE_LINUX_DEFAULT=\"quiet\"/GRUB_CMDLINE_LINUX_DEFAULT=\"quiet intel_iommu=on\"/g" /etc/default/grub
if (grep -qx "${find}" "${source}"); then
    sed -i "s/${find}/${replace}/g" "${source}"
    update-grub
    _REBOOT=$BS_TRUE
fi
echo $source
cat $source

source="/etc/initramfs-tools/modules"
list="vfio vfio_iommu_type1"
#list="${list} \"vfio_pci ids=1000:0064,1002:6819,1002:aab0,10de:1c03,10de:10f1\""
#list="${list} \"vfio_virqfd\""
for find in $list; do
    find=$(echo "${find}" | sed 's/"//g')
    if ! (grep -qx "${find}" "${source}"); then
        echo "${find}" >> "${source}"
        _REBOOT=$BS_TRUE
        _UPDATEIRFS=$BS_TRUE
    fi
done
list="\"vfio_pci ids=1000:0064,1002:6819,1002:aab0,10de:1c03,10de:10f1\""
for find in "${list}"; do
    find=$(echo "${find}" | sed 's/"//g')
    if ! (grep -qx "${find}" "${source}"); then
        echo "${find}" >> "${source}"
        _REBOOT=$BS_TRUE
        _UPDATEIRFS=$BS_TRUE
    fi
done
list="vfio_virqfd"
for find in "${list}"; do
    find=$(echo "${find}" | sed 's/"//g')
    if ! (grep -qx "${find}" "${source}"); then
        echo "${find}" >> "${source}"
        _REBOOT=$BS_TRUE
        _UPDATEIRFS=$BS_TRUE
    fi
done
echo $source
cat $source

source="/etc/modules"
for find in "vfio" "vfio_iommu_type1" "vfio_pci" "vfio_virqfd"; do
    if ! (grep -qx "${find}" "${source}"); then
        echo "${find}" >> "${source}"
        _REBOOT=$BS_TRUE
        _UPDATEIRFS=$BS_TRUE
    fi
done
echo $source
cat $source

source="/etc/modprobe.d/blacklist.conf"
for find in "blacklist radeon" "blacklist nouveau" "blacklist nvidia"; do
    if ! (grep -qx "${find}" "${source}"); then
        echo "${find}" >> "${source}"
        _REBOOT=$BS_TRUE
        _UPDATEIRFS=$BS_TRUE
    fi
done
echo $source
cat $source

source="/etc/modprobe.d/vfio.conf"
list="\"options vfio-pci ids=1000:0064,1002:6819,1002:aab0,10de:1c03,10de:10f1\""
for find in "${list}"; do
    find=$(echo "${find}" | sed 's/"//g')
    if ! (grep -qx "${find}" "${source}"); then
        echo "${find}" >> "${source}"
        _REBOOT=$BS_TRUE
        _UPDATEIRFS=$BS_TRUE
    fi
done
echo $source
cat $source

if [ "${_UPDATEIRFS}" -eq $BS_TRUE ]; then
    update-initramfs -u
    _UPDATEIRFS=$BS_FALSE
fi

echo "REBOOT: ${_REBOOT}"


