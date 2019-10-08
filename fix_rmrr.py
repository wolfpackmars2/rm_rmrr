#!/usr/bin/env python3
# ==============================================================================
# vim: softtabstop=4 shiftwidth=4 expandtab fenc=utf-8 cc=80 nu
# ==============================================================================
import argparse
import multiprocessing
import os
import sys
import subprocess
import ipaddress
import inspect
from shlex import split
from distutils.version import LooseVersion

root_path = os.path.dirname(os.path.realpath(__file__))
__VERSION = "2019.08.14-0"
__TEMPLATE_VERSION = 0
__TSEARCH = "debian-10"
__VENDOR_ID = "FA4D70"
__TEMPLATE_NAME = "rmrr-" + str(__TEMPLATE_VERSION) + "-{tname}"


class prettyprint:
    RC = ""
    GC = ""
    BC = ""
    YC = ""
    EC = ""
    message = "{c} * {t}{e}: {m}"

    def supports_color(self):
        """
        Returns True if the running system's terminal supports color, and False
        otherwise.
        """
        plat = sys.platform
        supported_platform = plat != 'Pocket PC' and (plat != 'win32' or
                                                      'ANSICON' in os.environ)
        # isatty is not always implemented, #6223.
        is_a_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
        return supported_platform and is_a_tty

    def p(self, msg, color=None, title=" Info"):
        if color is None:
            color = self.GC
        print(self.message.format(c=color, t=title, m=msg, e=self.EC))
        return

    def info(self, msg):
        self.p(msg)
        return

    def dp(self, msg):
        if self.debug:
            #print("{} * DEBUG{}: {}".format(self.BC, self.EC, msg))
            #print(self.message.format(c=self.BC, t='DEBUG', e=self.EC, m=msg))
            self.p(msg=msg, color=self.BC, title='DEBUG')
        return

    def err(self, msg):
        self.p(msg=msg, color=self.RC, title='ERROR')
        return

    def warn(self, msg):
        self.p(msg=msg, color=self.YC, title=' WARN')
        return

    def __init__(self, debug=False):
        self.debug = debug
        if self.supports_color():
            self.RC = '\033[1;31m'
            self.GC = '\033[1;32m'
            self.BC = '\033[1;34m'
            self.YC = '\033[1;33m'
            self.EC = '\033[0m'

    def __repr__(self):
        ret = {}
        ret['debug'] = self.debug
        ret['supports_color'] = self.supports_color()
        return str(ret)

    def __str__(self):
        ret = "PrettyPrint instance\n"
        ret = ret + "supports_color: {}\n".format(self.supports_color())
        ret = ret + "         debug: {}\n".format(self.debug)
        return ret


class kernel:
    # store information about a kernel
    def __repr__(self):
        ret = {}
        ret['pkg'] = self.pkg
        ret['hdr'] = self.hdr
        ret['versions'] = self.versions
        ret['installed'] = self.installed
        ret['active'] = self.active
        ret['source'] = self.source
        ret['selected'] = self.selected
        ret['available'] = self.available
        ret['policy'] = self.policy
        ret['exists'] = self.exists
        ret['upgradable'] = self.upgradable
        ret['customized'] = self.customized
        ret['git_url'] = self.git_url
        ret['git_hash'] = self.git_hash
        return str(ret)

    def __str__(self):
        ret = "{}\n".format(self.pkg)
        ret = ret + "pkg:".rjust(15, " ") + " {}\n".format(self.pkg)
        ret = ret + "hdr:".rjust(15, " ") + " {}\n".format(self.hdr)
        ret = ret + "exists:".rjust(15, " ") + " {}\n".format(self.exists)
        ret = ret + "versions:".rjust(15, " ") + " {}\n".format(self.versions)
        ret = ret + "available:".rjust(15, " ")
        ret = ret + " {}\n".format(self.available)
        ret = ret + "selected:".rjust(15, " ") + " {}\n".format(self.selected)
        ret = ret + "source:".rjust(15, " ") + " {}\n".format(self.source)
        ret = ret + "installed:".rjust(15, " ")
        ret = ret + " {}\n".format(self.installed)
        ret = ret + "active:".rjust(15, " ") + " {}\n".format(self.active)
        ret = ret + "upgradable:".rjust(15, " ")
        ret = ret + " {}\n".format(self.upgradable)
        ret = ret + "customized:".rjust(15, " ")
        ret = ret + " {}\n".format(self.customized)
        ret = ret + "git_url:".rjust(15, " ") + " {}\n".format(self.git_url)
        ret = ret + "git_hash:".rjust(15, " ") + " {}\n".format(self.git_hash)
        if not self.policy is None:
            ret = ret + "policy:".rjust(15, " ")
            # ret = ret + " {}\n".format(self.policy.splitlines()[0])
            for l in self.policy.splitlines():
                ret = ret + "\n{}{}".format(" " * 16, l)
        else:
            ret = ret + "policy:".rjust(15, " ") + " {}\n".format(self.policy)
        return ret

    def __init__(self, pkg=None, hdr=None):
        self._pkg = pkg
        self._hdr = hdr
        self._installed = None
        self._upgradable = None
        self._customized = None
        self._git_url = None
        self._git_hash = None
        self._selected = None
        self._source = None
        self._policy = None
        self._versions = None
        self._available = None
        self._exists = None
        self._update_apt = None
        self._active = None

    @property
    def pkg(self):
        """Name of package. String."""
        return self._pkg

    @property
    def hdr(self):
        """Name of header package. String."""
        return self._hdr

    @pkg.setter
    def pkg(self, pkg):
        if pkg == self._pkg:
            return
        self._pkg = pkg
        self._exists = None
        self._policy = None
        self._installed = None
        self._versions = None
        self._git_url = None
        self._git_hash = None
        self._customized = None
        self._active = None
        self._upgradable = None
        self._source = None

    @hdr.setter
    def hdr(self, hdr):
        if hdr == self._hdr:
            return
        self._hdr = hdr
        self._exists = None
        self._policy = None
        self._installed = None
        self._versions = None
        self._git_url = None
        self._git_hash = None
        self._customized = None
        self._active = None
        self._upgradable = None
        self._source = None

    @property
    def update_apt(self):
        """Updates apt. Returns True on success."""
        if not self._update_apt is None:
            return self._update_apt
        self._update_apt = None
        cmd = split("apt-get update")
        res = sp_run(cmd)
        # Update policy and exists
        self._exists = None
        self._policy = None
        if res.returncode == 0:
            return True
        else:
            return False

    @property
    def exists(self):
        """Return True if the package exists, otherwise False
        Uses apt-cache policy to determine if the package exists"""
        if not self._exists is None:
            return self._exists
        cmd = split("apt-cache policy {}".format(self.pkg))
        res = sp_run(cmd)
        self._exists = False
        if len(res.stdout.strip()) > 0:
            self._exists = True
        return self._exists

    @property
    def policy(self):
        """Get the output from apt-cache policy
        Returns None if the package information isn't available
        Otherwise returns the text from apt-cache stdout"""
        # cached result?
        if not self._policy is None:
            return self._policy
        self._policy = None
        if not self.exists:
            return None
        cmd = ("apt-cache policy {}".format(self.pkg))
        res = sp_run(cmd)
        if res.returncode == 0:
            self._policy = res.stdout
        return self._policy

    @property
    def installed(self):
        """Get installed version of the kernel package
        Returns None if the package doesn't exist
        Returns False if the package isn't installed
        Otherwise, returns the installed version"""
        # has result been cached?
        if not self._installed is None:
            return self._installed
        self._installed = None
        if not self.exists:
            return None
        pol = self.policy
        if pol is None:
            return None
        pol = pol.splitlines()
        for x in pol:
            if "Installed: " in x:
                self._installed = x.strip().split()[1]
                break
        if "none" in self._installed:
            self._installed = False
        return self._installed

    @property
    def versions(self):
        """Return list of known versions"""
        # has result been cached?
        if not self._versions is None:
            return self._versions
        if not self.exists:
            return None
        # default value
        self._versions = []
        pol = self.policy
        if pol is None:
            return None
        pol = pol.replace('***', '   ').splitlines()
        for x in pol:
            x = x.strip()
            if x == "" or x is None:
                # don't process blank lines
                continue
            if not "/" in x and not ":" in x:
                # don't process lines with '/' or ':'
                self._versions.append(x.split()[0])
        if len(self._versions) == 0:
            self._versions = None
        return self._versions

    @property
    def available(self):
        """Return highest version available. Returns None if package doesn't
        exist."""
        if not self._available is None:
            return self._available
        self._available = None
        if not self.exists:
            return None
        pol = self.policy
        if pol is None:
            return None
        pol = pol.splitlines()
        for x in pol:
            if "Candidate: " in x:
                self._available = x.strip().split()[1]
                break
        return self._available

    @property
    def selected(self):
        """Flag to denote whether this package is selected for action."""
        return self._selected

    @selected.setter
    def selected(self, selected):
        self._selected = selected

    @property
    def source(self):
        """Get contents of SOURCE file, which points to the specific source
        commit in Git for this particular kernel."""
        # has the result already been cached?
        if not self._source is None:
            return self._source
        # set default value
        self._source = None
        if not self.exists:
            return None
        # only available if this package is installed
        if not self.installed:
            return None
        # get location of SOURCE file
        cmd = split("dpkg -L {}".format(self.pkg))
        res = sp_run(cmd)
        cmd = split("grep /SOURCE")
        res = sp_run(cmd, input=res.stdout)
        if res.returncode == 0:
            res = res.stdout.splitlines()
            if len(res) > 0:
                with open(res[0].strip(), "r") as f:
                    slines = f.readlines()
                    self._source = None # set default as backup
                    self._git_url = None # same with git url and hash
                    self._git_hash = None
                    for x in slines:
                        x = x.strip()
                        if x.startswith("git clone"):
                            self._git_url = x.split()[2]
                        if x.startswith("git checkout"):
                            self._git_hash = x.split()[2]
                            self._source = x
        return self._source

    @property
    def git_url(self):
        """Returns the url of the Git repository for the package"""
        if not self._git_url is None:
            return self._git_url
        # for anything else we will call source as that will set the value
        self._git_url = None
        self._source = None
        self.source
        return self._git_url

    @property
    def git_hash(self):
        """Returns the hash of the commit the package is based on.
        Relies on source function to populate values."""
        if not self._git_hash is None:
            return self._git_hash
        # for anything else we will call source as that will set the value
        self._git_hash = None
        self._source = None
        self.source
        return self._git_hash

    @property
    def upgradable(self):
        """Returns True if an available version is higher than the installed
        version. False if the available version matches the installed version.
        Otherwise returns None."""
        if not self._upgradable is None:
            return self._upgradable
        self._upgradable = None
        #avail = self.available(refresh=refresh)
        self._installed = None
        if self.installed is None or self.installed == False:
            # not a valid pkg or package not installed
            return None
        self._available = None
        if self.available is None:
            # technically this shouldn't happen as self.installed would
            # have identified this as a non-existent package.
            return None
        # if we get here, then we should have a version for installed and a
        # version for available.
        v_compare = [self.installed, self.available]
        v_compare.sort(key=LooseVersion, reverse=True)
        if self.installed == v_compare[0]:
            # Installed version is the highest version available
            self._upgradable = False
        else:
            # Available version is higher than installed version
            self._upgradable = True
        return self._upgradable

    @property
    def customized(self):
        """Returns True if this package is not sourced from Proxmox or
        Debian repositories. Not yet implemented."""
        return False

    @property
    def active(self):
        """Query whether this package is the currently loaded kernel.
        Returns False if this package is not currently loaded.
        Returns True if the installed version is the same as the loaded kernel.
        Returns a version string if this is the active kernel, but a different
        version is installed than what is currently loaded. This would
        indicate that a reboot is pending to load the updated kernel.
        Any other case returns None."""
        # not yet implemented
        return False


class kernels(dict):
    def __repr__(self):
        return str(self.list)

    def __str__(self):
        ret = ""
        for k in self.keys():
            ret = ret + "{}\n{}".format(k, self[k])
        return ret

    def __init__(self):
        cmd = split('apt-cache search The Proxmox PVE Kernel Image')
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            res = list(res.stdout.splitlines())
            for x in res:
                if " - The Proxmox PVE Kernel Image" in x:
                    pkg = x.partition(" - ")[0]
                    self[pkg] = kernel(pkg=pkg)

    @property
    def list(self):
        return list(self.keys())


class pvenetwork:

    # Class variables: shared by all instances
    # https://pve.proxmox.com/pve-docs/pct.1.html
    # https://pve.proxmox.com/wiki/Manual:_pct.conf
    # https://pve.proxmox.com/pve-docs/pct-plain.html
    # https://pve.proxmox.com/pve-docs/pve-admin-guide.html#pct_container_network

    def __init__(self, id: int = 0, name: str = 'eth', bridge: int = None,
                 firewall: str = None, gateway: ipaddress.IPv4Address = None,
                 hwaddr: str = None, ip: ipaddress.IPv4Address = 'dhcp',
                 ip6: ipaddress.IPv6Address = None, mtu: int = None,
                 ratelimit: int = None, tagid: int = None, trunks: int = None,
                 nettype: str = 'veth'):
        # Instance variables
        self._id = None
        self._name = None
        self._bridge = None
        self._firewall = None
        self._gateway = None
        self._ip = None
        self._ip6 = None
        self._mtu = None
        self._ratelimit = None
        self._tagid = None
        self._trunks = None
        self._nettype = None
        self.id = id
        self.name = name
        self.bridge = bridge
        self.firewall = firewall
        self.gateway = gateway
        self.hwaddr = hwaddr
        self.ip = ip
        self.ip6 = ip6
        self.mtu = mtu
        self.ratelimit = ratelimit
        self.tagid = tagid
        self.trunks = trunks
        self.nettype = nettype
        return

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        # target:
        # -net0 "name=eth0,bridge=vmbr0,hwaddr=FA:4D:70:91:B8:6F,ip=dhcp,type=veth"
        ret = "-net{} \"name={}".format(self.id, self.name)
        if not self.bridge is None:
            ret = ret + ",bridge=vmbr{}".format(self.bridge)
        if not self.firewall is None:
            if self.firewall:
                ret = ret + ",firewall=1"
            else:
                ret = ret + ",firewall=0"
        if not self.gateway is None:
            ret = ret + ",gateway{}={}"
            if self.gateway.version == 4:
                ret = ret.format('', self.gateway.exploded)
            else:
                ret = ret.format('6', self.gateway.exploded)
        if not self.hwaddr is None:
            ret = ret + ",hwaddr={}".format(self.hwaddr)
        if not self.ip is None:
            if type(self.ip) is str:
                ret = ret + ",ip={}".format(self.ip)
            else:
                ret = ret + ",ip={}".format(self.ip.exploded)
        if not self.ip6 is None:
            if type(self.ip6) is str:
                ret = ret + ",ip6={}".format(self.ip6)
            else:
                ret = ret + ",ip6={}".format(self.ip6.exploded)
        if not self.mtu is None:
            ret = ret + ",mtu={}".format(self.mtu)
        if not self.ratelimit is None:
            ret = ret + ",rate={}".format(self.ratelimit)
        if not self.tagid is None:
            ret = ret + ",tagid={}".format(self.tagid)
        if not self.trunks is None:
            ret = ret + ",trunks={}".format(self.trunks)
        if not self.nettype is None:
            ret = ret + ",type={}".format(self.nettype)
        ret = ret + "\""
        return ret

    def gethwaddr(self, containerid: int) -> str:
        vendor = 'fa4d70'
        device = hex(containerid % 1048575).partition('x')[2].rjust(5, '0')
        self.hwaddr = "{}{}{}".format(vendor, self.id, device)
        return self.hwaddr

    def defaults(self, containerid: int) -> str:
        # sets good defaults and validates entries
        # name should be eth<id>
        # hwaddr should be 6 bytes
        # hwaddr default should be fa4d70TUUUUU
        # where T is the net<id> and UUUUU is the modulus of
        # containerid and 1048575 in hex
        print("type(self.hwaddr){}, type(containerid): {}".format(self.hwaddr,
                                                                  containerid))
        if type(self.hwaddr) is None and type(containerid) is int:
            vendor = 'fa4d70'
            print("vendor: {}".format(vendor))
            device = hex(containerid % 1048575).partition('x')[2].rjust(5, '0')
            print("device: {}".format(device))
            self.hwaddr = "{}{}{}".format(vendor, self.id, device)
            print("{}{}{}".format(vendor, self.id, device))
        if type(self.ip) is None and type(self.ip6) is None:
            self.ip = "dhcp"
        if self.name[0:3] == "eth" and int(self.name[3:]) != self.id:
            self.name = "eth{}".format(self.id)
        return self.string

    def tostring(self):
        return self.__str__()

    @property
    def string(self):
        return self.__str__()

    @property
    def nettype(self):
        return self._nettype

    @nettype.setter
    def nettype(self, nettype):
        # only nettype possible is 'veth'
        self._nettype = 'veth'
        return

    @property
    def trunks(self):
        return self._trunks

    @trunks.setter
    def trunks(self, trunks):
        if not type(trunks) is str:
            self._trunks = None
        else:
            self._trunks = trunks

    @property
    def tagid(self):
        return self._tagid

    @tagid.setter
    def tagid(self, tagid):
        if not type(tagid) is int or tagid < 1 or tagid > 4094:
            self._tagid = None
        else:
            self._tagid = tagid

    @property
    def ratelimit(self):
        return self._ratelimit

    @ratelimit.setter
    def ratelimit(self, ratelimit):
        if type(ratelimit) is int:
            self._ratelimit = abs(ratelimit)
        else:
            self._ratelimit = None

    @property
    def mtu(self):
        return self._mtu

    @mtu.setter
    def mtu(self, mtu):
        if type(mtu) is int:
            if mtu < 64:
                mtu = 64
            self._mtu = mtu
        else:
            self._mtu = None

    @property
    def ip6(self):
        return self._ip6

    @ip6.setter
    def ip6(self, ip6):
        if type(ip6) is str:
            try:
                self._ip6 = ipaddress.ip_address(ip6)
                if self._ip6.version == 4:
                    self._ip4 = self._ip6
                    self._ip6 = None
                return
            except:
                valid = ['auto', 'dhcp', 'manual']
                if ip6 in valid:
                    self._ip6 = ip6
                else:
                    self._ip6 = None
                return
        else:
            self._ip6 = None
            return

    @property
    def ip(self):
        return self._ip

    @ip.setter
    def ip(self, ip):
        try:
            self._ip = ipaddress.IPv4Network(ip)
        except:
            valid = ['dhcp', 'manual']
            if ip in valid:
                self._ip = ip
            else:
                self._ip = None

    @property
    def hwaddr(self):
        if self._hwaddr is None:
            return None
        ret = "{}:{}:{}:{}:{}:{}"
        hh = self._hwaddr.hex().rjust(12, '0').upper()
        ret = ret.format(hh[0:2],
                         hh[2:4],
                         hh[4:6],
                         hh[6:8],
                         hh[8:10],
                         hh[10:12])
        return ret

    @hwaddr.setter
    def hwaddr(self, hwaddr):
        tt = type(hwaddr)
        if tt is int:
            # convert to hex string
            hwaddr = hex(hwaddr).partition('x')[2].rjust(12, '0')
            self._hwaddr = bytes.fromhex(hwaddr[0:12])
            return
        elif tt is str:
            hwaddr = hwaddr.replace(':', '').replace('-', '').replace(' ', '')
            hwaddr = hwaddr.rjust(12, '0')
            self._hwaddr = bytes.fromhex(hwaddr[0:12])
            return
        elif tt is bytes:
            self._hwaddr = bytes.fromhex(hwaddr.hex().rjust(12, '0')[0:12])
            return
        else:
            self._hwaddr = None

    @property
    def gateway(self):
        return self._gateway

    @gateway.setter
    def gateway(self, gateway):
        try:
            self._gateway = ipaddress.ip_address(gateway)
        except:
            self._gateway = None

    @property
    def firewall(self):
        return self._firewall

    @firewall.setter
    def firewall(self, firewall):
        if not type(firewall) is bool:
            firewall = None
        self._firewall = firewall

    @property
    def bridge(self):
        return self._bridge

    @bridge.setter
    def bridge(self, bridge):
        if not type(bridge) is int:
            bridge = None
        elif bridge < 0 or bridge > 4094:
            bridge = None
        self._bridge = bridge

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, name):
        if not type(name) is str:
            name = None
            return
        if name[0:3] == 'eth':
            self._name = f'eth{self.id}'
            return
        self._name = name

    @property
    def id(self):
        return self._id

    @id.setter
    def id(self, id):
        if id is None:
            id = 0
        if not type(id) is int:
            id = 0
        if id > 9 or id < 0:
            id = 0
        self._id = id
        #update name if needed
        if type(self.name) is str and self.name[0:3] == "eth":
            self.name = "eth{}".format(id)
        return


class pvemountpoint:
    # https://pve.proxmox.com/pve-docs/pve-admin-guide.html#pct_mount_points

    def __repr__(self) -> str:
        return self.__str__()

    def __str__(self) -> str:
        # mp[n]: [volume=]<volume> ,mp=<Path> [,acl=<1|0>] [,backup=<1|0>]
        # [,mountoptions=<opt[;opt...]>] [,quota=<1|0>] [,replicate=<1|0>]
        # [,ro=<1|0>] [,shared=<1|0>] [,size=<DiskSize>]
        # "-mp0 \"{share},mp=/root/shared,ro=0\""
        ret: str = "-mp{} \"volume={}".format(self.id, self.volume)
        ret = "{},mp={}".format(ret, self.mp)
        if not self.acl is None:
            ret = "{},acl={}".format(ret, pve().pvebool(self.acl))
        if not self.backup is None:
            ret = "{},backup={}".format(ret, pve().pvebool(self.backup))
        if not self.quota is None:
            ret = "{},quota={}".format(ret, pve().pvebool(self.quota))
        if not self.replicate is None:
            ret = "{},replicate={}".format(ret, pve().pvebool(self.replicate))
        if not self.ro is None:
            ret = "{},ro={}".format(ret, pve().pvebool(self.ro))
        if not self.shared is None:
            ret = "{},shared={}".format(ret, pve().pvebool(self.shared))
        if not self.size is None:
            ret = "{},size={}".format(ret, self.size)
        ret = ret + "\""
        return ret

    def __init__(self, id: int = 0, acl: bool = None, backup: bool = None,
                 mp: str = None, quota: bool = None, replicate: bool = None,
                 ro: bool = None, shared: bool = None, size: int = None,
                 volume: str = None):
        self._id = None
        self._acl = None
        self._backup = None
        self._mp = None
        self._quota = None
        self._replicate = None
        self._ro = None
        self._shared = None
        self._size = None
        self._volume = None
        self.id = id
        self.acl = acl
        self.backup = backup
        self.mp = mp
        self.quota = quota
        self.replicate = replicate
        self.ro = ro
        self.shared = shared
        self.size = size
        self.volume = volume
        return

    @property
    def volume(self) -> str:
        return self._volume

    @volume.setter
    def volume(self, volume: str):
        self._volume = volume
        return

    @property
    def size(self) -> int:
        return self._size

    @size.setter
    def size(self, size: int):
        self._size = size
        return

    @property
    def shared(self) -> bool:
        return self._shared

    @shared.setter
    def shared(self, shared: bool):
        self._shared = pve().bool(shared)
        return

    @property
    def ro(self) -> bool:
        return self._ro

    @ro.setter
    def ro(self, ro: bool):
        self._ro = pve().bool(ro)
        return

    @property
    def replicate(self) -> bool:
        return self._replicate

    @replicate.setter
    def replicate(self, replicate: bool):
        self._replicate = pve().bool(replicate)
        return

    @property
    def quota(self) -> bool:
        return self._quota

    @quota.setter
    def quota(self, quota: bool):
        self._quota = pve().bool(quota)
        return

    @property
    def mp(self) -> str:
        return self._mp

    @mp.setter
    def mp(self, mp: str):
        self._mp = mp
        return

    @property
    def backup(self) -> bool:
        return self._backup

    @backup.setter
    def backup(self, backup: bool):
        self._backup = pve().bool(backup)
        return

    @property
    def acl(self) -> bool:
        return self._acl

    @acl.setter
    def acl(self, acl: bool):
        self._acl = pve().bool(acl)
        return

    @property
    def id(self) -> int:
        return self._id

    @id.setter
    def id(self, id: int):
        if not type(id) is int:
            raise TypeError("pvemountpoint.id must be int")
        if id < 0 or id > 9:
            raise ValueError("pvemountpoint.id must be between 0 and 9")
        self._id = id
        return

    @property
    def string(self) -> str:
        return self.__str__()

    def tostring(self):
        return self.__str__()


class pve:

    def __init__(self):
        pass

    def bool(self, var) -> bool:
        var = self.pvebool(var)
        if var == "1": return True
        elif var == "0": return False
        return None

    def isbool(self, var) -> bool:
        var = self.pvebool(var)
        if var == "1" or var == "0":
            return True
        else:
            return False
        return None # this will never happen. IDE sugar only.

    def pvebool(self, var) -> str:
        v = var
        t = type(v)  # t for Type
        if t is str or t is bool or t is int:
            if v == "1" or v == "t" or v == "T" or v == 1 or v is True:
                return "1"
            elif v == "0" or v == "f" or v == "F" or v == 0 or v is False:
                return "0"
        return None


class lxc:
    # "pct create {id} \"{tmpl}\" -storage {storage} -memory {ram} "
    #      "-net0 \"name=eth0,bridge=vmbr{bridge},hwaddr=FA:4D:70:91:B8:6F,"
    #      "ip=dhcp,type=veth\" -hostname buildr -cores {cores} -rootfs 80 "
    #      "-mp0 \"{share},mp=/root/shared,ro=0\""

    # documenting new lxc design
    # prop: net = pvenetwork or List[of pvenetwork] or None
    # prop: mp = pvemountpoint or List[of pvemountpoint] or None
    # prop: rootfs = pvemountpoint or None out=reqd
    # prop: hostname = str or None
    # prop: id = int; valid from 0 - 4094 or None out=reqd
    # prop: sshkey = str or None or List[of str]?
    # prop: privileged = bool or None
    # prop: cores = int or None
    # prop: cpulimit = decimal or None
    # prop: cpuunits = int; pve default is 1024
    # prop: onboot = bool or None(inherit); start at boot?; default False
    # prop: bootorder = int > 0; default None
    # prop: bootdelay = int > 0 or None; seconds
    # prop: deadtimeout = int > 0 or None; pve default is 60; seconds to wait
    #       after shutting down container before the shutdown action is
    #       reported as 'failed'
    # prop: description = str or None
    # prop: nesting = bool or None (nesting VM)
    # prop: keyctl = bool or None
    # prop: fuse = bool or None
    # prop: force = bool, default false. may not implement
    # prop: memory = int or None (use PVE default). ram in MB
    # prop: ostype = str [alpine|archlinux|centos|debian|fedora|gentoo|
    # prop:               opensuse|ubuntu|unmanaged] or None(inherit)
    # prop: password = str or None (root password)
    # prop: template = str or None out=reqd
    # prop: searchdomain = str or None
    # prop: ssh-public-keys = str or None or List[of str]. path to keyfile(s).
    #       path to openssh pubkey file. can contain multiple keys. only 1 file
    # prop: start = bool or none(inherit). Start after created
    # prop: startup = str or None [order=bootorder,up=bootdealy,down=deadt/o]
    # prop: storage = str or None(inherit) default pve is 'local'
    # prop: swap = int or None(inherit) vm swap in mb. pve default = 512MB
    # prop: tty = int 0 to 6 or None(inherit) pve default is 2
    #       count of tty available to container
    # prop: unique = bool or None. assign random ethernet address.
    #       requires restore option



    #def __repr__(self):
    #    return self.create(test=True)

    def __str__(self):
        #ret = ""
        #d = self.__dict__
        #maxl = len(max(d.keys())) + 4
        #for x in d:
        #    ret = ret + "{}: {}\n".format(str(x).rjust(maxl), str(d[x]))
        var = inspect.classify_class_attrs(lxc)
        ret = ""
        for item in var:
            if item.kind == 'property':
                val = getattr(self, item.name)
                ret = f"{ret}{item.name}: {val}\n"
        return ret.strip()

    def __init__(self, id: int = 500, cores: int = None, ram: int = None,
                 tmpl: str = "debian-10", storage: str = "local-lvm",
                 mp: pvemountpoint = None, net: pvenetwork = None,
                 fssize: int = 80, hostname: str = None,
                 description: str = None):
        self._returnlist = []
        self._id = None
        self._cores = None
        self._ram = None
        self._tmpl = None
        self._storage = None
        self._mp = None
        self._net = None
        self._fssize = None
        self._hostname = None
        self._description = None
        self.id = id
        self.cores = cores
        self.ram = ram
        self.tmpl = tmpl
        self.storage = storage
        self.mp = mp
        self.net = net
        self.fssize = fssize
        self.hostname = hostname
        self.description = description
        return

    def runcmd(self, cmd: str) -> subprocess.CompletedProcess:
        cmd = split(cmd)
        if len(self._returnlist) > 9:
            self._returnlist.pop()
        self._returnlist.insert(0, sp_run(cmd))
        return self._returnlist[0]

    @property
    def lastcmd(self) -> list:
        if len(self._returnlist) > 0:
            return self._returnlist[0].args
        return None

    @property
    def lastresult(self) -> subprocess.CompletedProcess:
        if len(self._returnlist) > 0:
            return self._returnlist[0]
        return None

    @property
    def configfile(self) -> str:
        # Get the location of the LXC config file
        # found in /etc/pve/nodes/pve/lxc/<id>.conf
        # if file exists, return path the file as str
        # otherwise return None
        ret = "/etc/pve/nodes/pve/lxc/{}.conf".format(self.id)
        if os.path.isfile(ret):
            return ret
        else:
            return None

    @property
    def configfilecontents(self) -> str:
        # if configfile exists, return its contents
        # otherwise return None
        cfg = self.configfile
        if cfg is None: return None
        ret = None
        with open(cfg, 'r') as cfgfile:
            ret = cfgfile.read()
        return ret

    @property
    def status(self) -> str:
        # returns the status of the container or None if the container doesn't
        # exist.
        # if configfile exists, run pct status <id> which returns one of
        #   status: stopped
        #   status: running
        #   Configuration file 'nodes/pve/lxc/<id>.conf' does not exist
        if self.configfile is None: return None
        cmd = "pct status {}".format(self.id)
        ret = self.runcmd(cmd).stdout.partition(":")[2].strip()
        if not type(ret) is str or ret == "": return None
        return ret

    @property
    def id(self) -> int:
        return self._id

    @id.setter
    def id(self, id: int):
        if type(id) is int:
            self._id = id
        else:
            self._id = 500
        return

    @property
    def cores(self) -> int:
        return self._cores

    @cores.setter
    def cores(self, cores: int):
        c = multiprocessing.cpu_count()
        if cores is None or not type(cores) is int:
            if c > 10:
                self._cores = c - 4
                return
            elif c > 2:
                self._cores = c - 2
                return
            else:
                self._cores = c
                return
        elif cores > c:
            self._cores = c
            return
        # if we get here, use the value passed in
        self._cores = cores
        return

    @property
    def ram(self) -> int:
        return self._ram

    @ram.setter
    def ram(self, ram: int):
        # in GB
        if ram is None:
            cmd = split('free -t -m')
            res = sp_run(cmd)
            if res.returncode == 0:
                r = int(res.stdout.splitlines()[-1].split()[3]) // 1024
            else:
                r = 4
            if r > 8:
                self._ram = 6 * 1024
                if self.cores > 80:
                    # limit cores to 80 or increase ram to 16GB
                    if r > 18:
                        self._ram = 16 * 1024
                    else:
                        self.cores = 80
            else:
                # we do not have more than 8GB of free ram; limit resources
                self._ram = 4 * 1024
        else:
            self._ram = ram * 1024
        return

    @property
    def tmpl(self) -> str:
        return self._tmpl

    @tmpl.setter
    def tmpl(self, tmpl: str):
        templates = []
        res = self.runcmd('pveam update')
        res = self.runcmd('pveam available -section system')
        for x in res.stdout.splitlines():
            x = x.lower()
            if tmpl in x:
                templates.append(x.rpartition(" ")[2].strip())
        if len(templates) > 0:
            templates.sort(key=LooseVersion, reverse=True)
            self.runcmd(f"pveam download local {templates[0]}")
        res = self.runcmd("pveam list local").stdout.partition("\n")[2]
        templates = []
        for x in res.splitlines():
            if tmpl in x:
                templates.append(x.split()[0])
        if len(templates) > 0:
            templates.sort(key=LooseVersion, reverse=True)
            self._tmpl = templates[0]
            return
        else:
            self._tmpl = None
            return
        return

    @property
    def storage(self) -> str:
        return self._storage

    @storage.setter
    def storage(self, storage: str):
        self._storage = storage
        return

    @property
    def mp(self) -> pvemountpoint:
        return self._mp

    @mp.setter
    def mp(self, mp: pvemountpoint):
        t = type(mp)
        if t is list and len(mp) > 0:
            # self.mp is a list. each list object needs to be tested and any
            # duplicate values will be rejected
            validmounts = []
            mountids = set(None)
            mountmps = set(None)
            for mount in mp:
                # mountpoint requirements
                # mount.id is not null and not duplicated in the list(mp)
                # mount.volume is not null and not duplicated in the list
                # mount.mp is not null and not duplicated in the list
                if type(mount) is pvemountpoint \
                   and not mount.id in mountids \
                   and not mount.volume in mountids \
                   and not mount.mp in mountmps:
                    # tests passed, update the sets and add to the validmounts
                    # list.
                    mountids.add(mount.id)
                    mountids.add(mount.volume)
                    mountmps.add(mount.mp)
                    validmounts.append(mount)
            if len(validmounts) > 0:
                # at least one mp in the list is valid. replace the object in
                # self with the new list containing validated pvemountpoints.
                self._mp = validmounts
                return
            else:
                # self.mp is invalid type. set to none. test failed
                self._mp = None
                return
        elif t is pvemountpoint:
            if mp.id is None or mp.volume is None or mp.mp is None:
                # mountpoint cannot have null id, volume or mountpoint
                # test failed; set mp to none
                self._mp = None
                return
            else:
                self._mp = mp
                return
        else:
            # passed in value is not a list or a pvemountpoint, thus invalid
            self._mp = None
        return

    @property
    def net(self) -> pvenetwork:
        return self._net

    @net.setter
    def net(self, net: pvenetwork):
        t = type(net)
        # validate network settings
        if t is list and len(net) > 0:
            validnets = []
            netids = set(None)
            for n in net:
                if type(n) is pvenetwork:
                    if n.hwaddr is None:
                        n.hwaddr = "fa4d70000000"
                    n.defaults(self.id)
                    if not n.id in netids and not n.hwaddr in netids \
                       and not n.name in netids:
                        netids.add(n.id)
                        netids.add(n.hwaddr)
                        netids.add(n.name)
                        validnets.append(n)
            if len(validnets) > 0:
                self._net = validnets
                return
            else:
                self._net = None
                return
        elif t is pvenetwork:
            if net.hwaddr is None:
                net.gethwaddr(self.id)
            #net.defaults(self.id)
            self._net = net
            return
        else:
            self._net = None
            return
        return

    @property
    def fssize(self) -> int:
        return self._fssize

    @fssize.setter
    def fssize(self, fssize: int):
        self._fssize = fssize
        return

    @property
    def hostname(self) -> str:
        return self._hostname

    @hostname.setter
    def hostname(self, hostname: str):
        self._hostname = hostname
        return

    @property
    def description(self) -> str:
        return self._description

    @description.setter
    def description(self, description: str):
        self._description = description
        return

    def start(self) -> subprocess.CompletedProcess:
        # return True on success, error otherwise
        cmd = f"pct start {self.id}"
        return self.runcmd(cmd)

    def stop(self) -> subprocess.CompletedProcess:
        cmd = f"pct stop {self.id}"
        return self.runcmd(cmd)

    def restart(self) -> subprocess.CompletedProcess:
        self.stop()
        self.start()
        ret = self._returnlist[0:2]
        ret.reverse()
        return ret

    def create(self, overwrite: bool = False,
               test: bool = False) -> subprocess.CompletedProcess:
        # True on success, str error otherwise
        # test: output shell command to console but don't execute
        if not self.hostname: self.hostname = "bildr"
        cmd = f"pct create {self.id} \"{self.tmpl}\" -storage {self.storage} "
        cmd = f"{cmd} -memory {self.ram} -hostname {self.hostname} "
        cmd = f"{cmd} -cores {self.cores} -rootfs {self.fssize}"
        if self.mp:
            if type(self.mp) is list:
                for i in self.mp:
                    cmd = f"{cmd} {i}"
            else:
                cmd = f"{cmd} {self.mp}"
        if self.net:
            if type(self.net) is list:
                for i in self.net:
                    cmd = f"{cmd} {i}"
            else:
                cmd = f"{cmd} {self.net}"
        if not test:
            # run the command
            if overwrite and self.status:
                # status returns None if VM doesn't exist
                self.destroy()
            return runcmd(cmd)
        return cmd

    def destroy(self, test: bool = True) -> subprocess.CompletedProcess:
        cmd = f"pct destroy {self.id}"
        if test:
            returnstr = f"No actions were taken. Call 'destroy(test=False)' to"
            returnstr = f"{returnstr} run the following command:\n{cmd}"
            return returnstr
        self.stop()
        return self.runcmd(cmd)

    def set_defaults(self):
        if self.id == 0: self.id = 500
        if self.net is None: self.net = pvenetwork(bridge=0, id=0, ip="dhcp")
        if self.mp is None:
            self.mp = pvemountpoint(ro=0, id=0, mp='/root/shared',
                                    volume = f"{root_path}/shared")
        if self.hostname is None: self.hostname = "bildr"
        if self.tmpl is None: self.tmpl = "debian-10"
        if self.storage is None:
            self.storage = "local-lvm"


def sp_run(cmd, capture_output=True, timeout=None,
           check=False, encoding=None, 
           text=True, **kwargs) -> subprocess.CompletedProcess:
    if type(cmd) is str:
        cmd = split(cmd)
    #pprint.dp("cmd: {}".format(cmd))
    return subprocess.run(cmd, capture_output=capture_output,
                          timeout=timeout, check=check, encoding=encoding,
                          text=text, **kwargs)


def header(pp):
    pprint.p("Script Version: {}".format(__VERSION))
    pprint.p("Template Version: {}".format(__TEMPLATE_VERSION))
    pprint.p("-------------------------------------------\n")


def get_template(name='debian-10', update=False, storage=None):
    pprint.dp("get_template.name: {}".format(name))
    pprint.dp("get_template.update: {}".format(update))
    pprint.dp("get_template.storage: {}".format(storage))
    d = {}
    d['search'] = name.lower()
    d['name'] = ""
    d['storage'] = None
    d['fullname'] = "local:vztmpl/debian-10.0-standard_10.0-1_amd64.tar.gz"
    # get list of template storage
    #cmd = split('pvesm status -content vztmpl')
    res = sp_run('pvesm status -content vztmpl').stdout.partition("\n")[2]
    if storage is None:
        d['storage'] = res.splitlines()[0].split()[0]
    else:
        for x in res.splitlines():
            x = x.split()[0]
            if storage == x:
                d['storage'] = x
                break
    if d['storage'] is None:
        d['storage'] = 'local'
    res = sp_run('pveam list {}'.format(d['storage']))
    res = res.stdout.partition("\n")[2]
    if d['search'] in res:
        res_list = []
        for x in res.splitlines():
            if d['search'] in x.lower():
                res_list.append(x.split()[0])
        if len(res_list) > 0:
            res_list.sort(key=LooseVersion, reverse=True)
            d['fullname'] = res_list[0]
            d['storage'] = d['fullname'].partition(":")[0]
            d['name'] = d['fullname'].rpartition("/")[2]
        else:
            update = True
    else:
        update = True
    if update:
        subprocess.run(split('pveam update'))
        cmd = split('pveam available -section system')
        pprint.dp("cmd: {}".format(cmd))
        res = subprocess.run(cmd, capture_output=True,
                             text=True).stdout.splitlines()
        _AVAIL = []
        for tmpl in res:
            tmpl = tmpl.rpartition(" ")[2].strip().lower()
            if name in tmpl:
                _AVAIL.append(tmpl)
        if len(_AVAIL) > 0:
            # check if update required
            _AVAIL.sort(key=LooseVersion, reverse=True)
        pprint.p("Downloading template: {}".format(_AVAIL[0]))
        cmd = split('pveam download local {}'.format(_AVAIL[0]))
        pprint.dp("cmd: {}".format(cmd))
        res = subprocess.run(cmd, capture_output=True, text=True)
        pprint.dp("res: {}".format(res))
        pprint.dp("_AVAIL[0]: {}".format(_AVAIL[0]))
    cmd = split('pveam list local')
    pprint.dp("cmd: {}".format(cmd))
    res = subprocess.run(cmd, capture_output=True,
                         text=True).stdout.splitlines()[1:]
    pprint.dp("res: {}".format(res))
    _AVAIL = []
    for x in res:
        pprint.dp("x: {}".format(x))
        if __TSEARCH in x:
            x = x.split()[0]
            pprint.dp("x: {}".format(x))
            #_AVAIL[x.partition("/")[2]] = x
            _AVAIL.append(x)
            pprint.dp("_AVAIL: {}\n".format(_AVAIL))
    pprint.dp("_AVAIL Final: {}\n".format(_AVAIL))
    _AVAIL.sort(key=LooseVersion, reverse=True)
    pprint.dp("template: {}".format(_AVAIL[0]))
    return _AVAIL[0]


def write_bootstrap_scripts(output_dir, target_kernel):
    """Creates the scripts to be run on the VM/LXC"""
    # Skeleton for new script files
    #output_file = "{}/gitinit.sh".format(output_dir)
    # script = ("#!/bin/sh -"
    #          "\n" + "if ! [ \"$(id -u)\" -eq 0 ]; then"
    #          "\n" + "    echo Must be root"
    #          "\n" + "    exit 1"
    #          "\n" + "fi"
    #          "\n" + "# include variables from conf file, if exist"
    #          "\n" + "startdir=$(pwd -P)"
    #          "\n" + "conffile=\"" + conf_file + "\""
    #          "\n" + "gitdir=\"" + git_dir + "\""
    #          "\n" + "if [ -f \"$conffile\" ]; then"
    #          "\n" + "    source \"$conffile\""
    #          "\n" + "fi"
    #          "\n" + ""
    #          "\n" + "cd \"${startdir}\"")
    #pprint.dp("script: {}".format(script))
    # with open(output_file, "w") as script_file:
    #    script_file.write(script)
    #    pprint.dp("File written: {}".format(output_file))

    git_dir = "/root/shared/git"
    conf_file = "/root/shared/bootstrap.conf"

    output_file = "{}/bootstrap.sh".format(output_dir)
    script = ("#!/bin/sh -\n"
              "if ! [ \"$(id -u)\" -eq 0 ]; then\n"
              "    echo Must be root" + "\n"
              "    exit 1" + "\n"
              "fi" + "\n"
              "startdir=$(pwd -P)" + "\n"
              "gitdir=\"" + git_dir + "\"\n"
              "conffile=\"" + conf_file + "\""
              "\n" + "if [ -f \"${conffile}\" ]; then"
              "\n" + "    source \"${conffile}\""
              "\n" + "fi"
              "# Check Locale" + "\n"
              "if (locale 2>&1 | grep \"locale: Cannot set\"); then" + "\n"
              "    echo \"Fixing Locales\"" + "\n"
              "    echo \"en_US.UTF-8 UTF-8\" >> /etc/locale.gen" + "\n"
              "    locale-gen" + "\n"
              "    update-locale LANG=en_US.UTF-8 UTF-8" + "\n"
              "    dpkg-reconfigure --frontend=noninteractive locales" + "\n"
              "fi" + "\n"
              "# Install lsbrelease" + "\n"
              "if ! (command -v \"lsb_release\" > /dev/null 2>&1); then" + "\n"
              "    apt update" + "\n"
              "    apt install lsb-release -y --frontend=noninteractive" + "\n"
              "fi" + "\n"
              "# Check repos" + "\n"
              "gpg_key=\"proxmox-ve-release-6.x.gpg\"" + "\n"
              "pve_repo=\"deb http://download.proxmox.com/debian/pve buster "
              "pve-no-subscription\"" + "\n"
              "wget \"http://download.proxmox.com/debian/$gpg_key\" -O "
              "\"/etc/apt/trusted.gpg.d/$gpg_key\"" + "\n"
              "echo \"$pve_repo\" > /etc/apt/sources.list.d/pve.list" + "\n"
              "apt-get update || (echo \"Something went wrong\" && exit 1)"
              "\n" + "echo \"Installing apt updates\""
              "\n" + "apt-get dist-upgrade -y --frontend=noninteractive"
              "\n" + "pkgs=\"build-essential\""
              "\n" + "pkgs=\"$pkgs patch\""
              "\n" + "pkgs=\"$pkgs debhelper\""
              "\n" + "pkgs=\"$pkgs libpve-common-perl\""
              "\n" + "pkgs=\"$pkgs pve-kernel-5.0\""
              "\n" + "pkgs=\"$pkgs pve-doc-generator\""
              "\n" + "pkgs=\"$pkgs git\""
              #"\n" + "pkgs=\"$pkgs \""
              "\n" + "DEBIAN_FRONTEND=noninteractive apt-get install -y $pkgs"
              "\n" + "if ! [ -d \"${gitdir}\" ]; then"
              "\n" + "    mkdir -p \"${gitdir}\""
              "\n" + "fi"
              "\n" + "cd \"${gitdir}\""
              #"\n" + "if ! [ -d \"kernel\" ]; then (mkdir \"kernel\"); fi"
              #"\n" + "cd kernel"
              "\n" + "git clone git://git.proxmox.com/git/pve-kernel.git"
              "\n" + "if ! [ -f \"${conffile}\" ]; then"
              "\n" + "    echo \"gitdir=${gitdir}\" > ${conffile}"
              "\n" + "fi"
              "\n" + "cd \"${startdir}\"")
    pprint.dp("script: {}".format(script))
    with open(output_file, "w") as script_file:
        script_file.write(script)
        pprint.dp("File written: {}".format(output_file))
    output_file = "{}/gitinit.sh".format(output_dir)
    script = ("#!/bin/sh -"
              "\n" + "if ! [ \"$(id -u)\" -eq 0 ]; then"
              "\n" + "    echo Must be root"
              "\n" + "    exit 1"
              "\n" + "fi"
              "\n" + "# include variables from conf file, if exist"
              "\n" + "startdir=$(pwd -P)"
              "\n" + "conffile=\"" + conf_file + "\""
              "\n" + "gitdir=\"" + git_dir + "\""
              "\n" + "kernel_git_url=\"\""
              "\n" + "kernel_git_hash=\"\""
              "\n" + "if [ -f \"$conffile\" ]; then"
              "\n" + "    source \"$conffile\""
              "\n" + "fi"
              "\n" + "cd \"$gitdir\""
              "\n" + "if ! [ -d \"${gitdir}/pve-kernel"
              "\n" + "cd pve-kernel"
              "\n" + "if kernel_git_url == \"\"; then exit 1"
              "\n" + "if kernel_git_hash == \"\"; then exit 1"
              "\n" + "git checkout $kernel_git_hash"
              "\n" + ""
              "\n" + ""
              "\n" + ""
              "\n" + ""
              "\n" + ""
              "\n" + ""
              "\n" + "cd \"${startdir}\"")
    pprint.dp("script: {}".format(script))
    if type(target_kernel) is kernel:
        with open(output_file, "w") as script_file:
            script_file.write(script)
            pprint.dp("File written: {}".format(output_file))
        output_file = "{}/bootstrap.conf".format(output_dir)
        script = ("#!/bin/sh -"
                  "\n" + "kernel_git_url=\"" + target_kernel.git_url + "\""
                  "\n" + "kernel_git_hash=\"" + target_kernel.git_hash + "\"")
        with open(output_file, "w") as script_file:
            script_file.write(script)
            pprint.dp("File written: {}".format(output_file))


def create_lxc(cont, tmpl, storage='local-lvm'):
    pprint.dp("f: create_lxc")

    cmd = ("pct create {id} \"{tmpl}\" -storage {storage} -memory {ram} "
           "-net0 \"name=eth0,bridge=vmbr{bridge},hwaddr={hwaddr},"
           "ip=dhcp,type=veth\" -hostname buildr -cores {cores} -rootfs 80 "
           "-mp0 \"{share},mp=/root/shared,ro=0\"")
    cmd = cmd.format(id=cont.id,
                     hwaddr=machwaddr,
                     tmpl=tmpl,
                     storage=storage,
                     ram=cont.ram * 1024,
                     bridge=cont.bridge_id,
                     cores=cont.cores,
                     share=cont.shared_dir)
    # cmd = cmd.format(id=cont.id, tmpl=tmpl, storage=storage, ram=cont.ram,
    #                 bridge=cont.bridge_id, cores=cont.cores,
    #                 share=cont.shared_dir)
    if os.path.exists(cont.shared_dir):
        # shared_dir object already exists. is it a directory?
        if not os.path.isdir(cont.shared_dir):
            # shared_dir object exists but is not a directory. stop
            return False
        # shared directory exists, overwrite?
    else:
        # shared_dir doesn't exist, create it
        os.makedirs(cont.shared_dir)
    pprint.dp("cmd: {}".format(cmd))
    cmd = split(cmd)
    pprint.dp("cmd: {}".format(cmd))
    pprint.p("Created LXC {}".format(cont.id))
    # pdb.set_trace()
    res = sp_run(cmd)
    if res.returncode == 0:
        pprint.dp("LXC Create result: {}".format(res.stdout))
        return True
    pprint.dp("LXC Create error: {}".format(res.stderr))
    return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Setup build environment for\
                                     building custom PVE Kernels")

    parser.formatter_class = argparse.MetavarTypeHelpFormatter

    parser.add_argument("-v",
                        "--verbose",
                        help="Show debugging messages",
                        action="store_true")

    parser.add_argument("-b",
                        "--bridge",
                        help="Bridge # to connect to",
                        type=int,
                        default=0)

    parser.add_argument("-i",
                        "--id",
                        help="LXC ID to use",
                        type=int,
                        default=500)

    parser.add_argument("-f",
                        "--force",
                        help="Overwrite existing LXC without prompting",
                        action="store_true")

    parser.add_argument("-C",
                        "--cores",
                        help="Number of cores to use. Default <cores> - 4",
                        type=int,
                        default=(multiprocessing.cpu_count() - 4))

    parser.add_argument("-R",
                        "--ram",
                        help="Amount of ram in GB",
                        type=int,
                        default=6)

    parser.add_argument("-K",
                        "--kernel",
                        help="Kernel package search string to target",
                        type=str,
                        default=None)

    parser.add_argument("-V",
                        "--version",
                        help="Show version and exit",
                        action="store_true")

    parser.add_argument("-M",
                        "--mac",
                        help="Specify network MAC Vendor ID in hex. "
                        "6 Hex Characters without separators. "
                        "e.g.: 00008F "
                        "default: FA4D70 "
                        "This is the first 6 characters of the VM MAC ID. ",
                        type=str,
                        default="FA4D70")

    parser.add_argument("-S",
                        "--share",
                        help="Path to shared folder",
                        type=str,
                        default="{}/shared".format(root_path))

    args = parser.parse_args()

    pprint = prettyprint(args.verbose)

    header(pprint)

    # validate mac-vendor id
    if args.mac:
        mm = args.mac
        mm = mm.replace('-', '')  # remove dashes
        mm = mm.replace(':', '')  # remove colons
        if len(mm) > 6:
            sys.exit("Vendor MAC ID too long.")
        try:
            int(mm, 16)
        except ValueError:
            sys.exit("Invalid Vendor MAC ID specified.")
        # all checks pass, set mac_vendor
        __MAC_VENDOR = mm.rjust(6, '0')

    pprint.dp(args)
    # pprint.dp(args.bridge)
    # pprint.dp(pprint.supports_color())
    #tmpl = get_template()
    #pprint.dp("tmpl: {}".format(tmpl))
    #cont = lxc(lxc_id=args.id, shared_dir=args.share)
    cont = lxc(id=args.id, net=pvenetwork(bridge=0, ip='dhcp'),
               mp=pvemountpoint(volume=args.share, mp="/root/shared", ro=0))
    cont.set_defaults() # set any required settings
    pprint.dp("cont:\n{}".format(cont))
    #if create_lxc(cont, tmpl):
    #    cmd = split('pct start {}'.format(cont.id))
    #    res = sp_run(cmd)
    #    pprint.dp("cmd output: {}".format(res))
    if not cont.status:
        pprint.dp("lxc.create: {}".format(cont.create()))
    elif args.force:
        s = ("lxc.create [forced]:\n{}".format(cont.create(overwrite=True)))
        pprint.dp(s)
    k = kernels()
    l = kernels.list
    l.sort(key=LooseVersion, reverse=True)
    krnl = None
    if args.kernel:
        # User specified a kernel search string to use
        # go through the list of kernels to find the specified string
        for ll in l:
            if args.kernel in ll:
                krnl = k[ll]
                break
        if not krnl:
            exitstring = "The specified kernel \"{}\" was not found."
            sys.exit(exitstring.format(args.kernel))
    if not krnl:
        for ll in l:
            if k[ll].installed:
                krnl = k[ll]
                break
    if not krnl:
        # something went wrong, unable to find an installed kernel
        sys.exit("Unable to find a kernel to work with")
    script = write_bootstrap_scripts(cont.shared_dir, 'x')
    # a file exists in the pve kernel package which specifies the git id
    # the package was built against
    # next step is to figure out which build was used and git checkout
    # that build.
    # after that, determine which sub-projects to download
    # after that, determine which packages still need to be installed
    # after that, make! profit :)
    # 2019.08.30 - rewrote class Kernel. Most operation in class Kernels
    #   is no longer necessary. Next step is to rework class Kernels.
    #   also need to review class Kernel and remove any unecessary code.
    sys.exit()

