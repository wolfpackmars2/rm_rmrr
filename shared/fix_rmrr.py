#!/usr/bin/env python3
#==============================================================================
# vim: softtabstop=4 shiftwidth=4 expandtab fenc=utf-8 cc=80 nu
#==============================================================================
import argparse, multiprocessing, os, sys, subprocess
from shlex import split
from distutils.version import LooseVersion

root_path = os.path.dirname(os.path.realpath(__file__))
__VERSION = "2019.08.14-0"
__TEMPLATE_VERSION = 0
__TSEARCH = "debian-10"
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

    def p(self, msg, color = None, title = " Info"):
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
            self.p(msg = msg, color = self.BC, title = 'DEBUG')
        return

    def err(self, msg):
        self.p(msg = msg, color = self.RC, title = 'ERROR')
        return

    def warn(self, msg):
        self.p(msg = msg, color = self.YC, title = ' WARN')
        return

    def __init__(self, debug = False):
        self.debug = debug
        if self.supports_color():
            self.RC = '\033[1;31m'
            self.GC = '\033[1;32m'
            self.BC = '\033[1;34m'
            self.YC = '\033[1;33m'
            self.EC = '\033[0m'

class kernel:
    # store information about a kernel
    def __repr__(self):
        ret = {}
        ret['pkg'] = self.pkg
        ret['hdr'] = self.hdr
        ret['version'] = self.version
        ret['installed'] = self.installed
        ret['installed_version'] = self.installed_version
        ret['active'] = self.active
        ret['upgradable'] = self.upgradable
        ret['customized'] = self.customized
        ret['git_url'] = self.git_url
        ret['git_hash'] = self.git_hash
        return str(ret)

    def __str__(self):
        ret = "{}\n".format(self.pkg)
        ret = ret + "                pkg: {}\n".format(self.pkg)
        ret = ret + "                hdr: {}\n".format(self.hdr)
        ret = ret + "            version: {}\n".format(self.version)
        ret = ret + "          installed: {}\n".format(self.installed)
        ret = ret + "  installed_version: {}\n".format(self.installed_version)
        ret = ret + "             active: {}\n".format(self.active)
        ret = ret + "         upgradable: {}\n".format(self.upgradable)
        ret = ret + "         customized: {}\n".format(self.customized)
        ret = ret + "            git_url: {}\n".format(self.git_url)
        ret = ret + "           git_hash: {}".format(self.git_hash)
        return ret

    def __init__(self, pkg=None, hdr=None, version=None, git_url=None,
                 git_hash=None, installed=False, upgradable=False,
                 customized=False):
        self.pkg = pkg
        self.hdr = hdr
        self.version = version
        self.installed = installed
        self.active = False
        self.upgradable = upgradable
        self.customized = customized
        self.installed_version = None
        self.git_url = git_url
        self.git_hash = git_hash


class kernels:

    def __get_source__(self, pkg):
        cmd = split('dpkg --search {}'.format(pkg))
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            return None
        # pve-kernel-5.0.18-1-pve:
            # /usr/share/doc/pve-kernel-5.0.18-1-pve/SOURCE
        res = res.stdout
        if not 'SOURCE' in res:
            return None
        res = res.splitlines()
        source_file = None
        for x in res:
            if 'SOURCE' in x:
                source_file = x.split(": ")[1]
                break
        cmd = split('cat {}'.format(source_file))
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            return None
        res = res.stdout.splitlines()
        git_url = None
        git_hash = None
        for x in res:
            if 'git clone ' in x:
                git_url = x.rpartition(" ")[2]
            if 'git checkout ' in x:
                git_hash = x.rpartition(" ")[2]
        if not git_url or not git_hash:
            return None
        return {'url': git_url, 'hash': git_hash}

    def __get_kernel_details__(self, pkg):
        krnl = kernel(pkg=pkg)
        cmd = split('apt-cache policy {}'.format(pkg))
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            return None
        res = res.stdout.splitlines()
        krnl.installed_version = res[1].split(": ")[1]
        if krnl.installed_version == '(none)':
            krnl.installed = False
            krnl.installed_version = None
            krnl.upgradable = True
        else:
            krnl.installed = True
        krnl.version = res[2].split(": ")[1]
        if krnl.version != krnl.installed_version:
            krnl.upgradable = True
        krnl.hdr = krnl.pkg.replace('-kernel-', '-headers-')
        if krnl.installed:
            src = self.__get_source__(pkg)
            if src is not None:
                krnl.git_url = src['url']
                krnl.git_hash = src['hash']
        return krnl
        # krnl.customized

    def __get_pkg_details__(self, pkg):
        return self.__get_kernel_details__(pkg)

    def __get_kernel_meta__(self):
        cmd = split('apt-cache search Latest Proxmox')
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0 or \
           not ' - Latest Proxmox VE Kernel Image' in res.stdout:
            return None
        res = list(res.stdout.splitlines())
        meta = {}
        for x in res:
            if ' - Latest Proxmox VE Kernel Image' in x:
                pkg = x.partition(" - ")[0]
                meta["pkg"] = pkg
                pkg = self.__get_pkg_details__(pkg)
                meta["installed"] = pkg.installed_version
                meta["available"] = pkg.version
                meta["updatable"] = pkg.upgradable
                self.installed.append(pkg)
                cmd = split('apt-cache show {}'.format(meta['pkg']))
                res = subprocess.run(cmd, capture_output=True, text=True)
                if res.returncode != 0:
                    return None
                lst = res.stdout.split('\n\n')
                for x in lst:
                    if not 'Version: {}'.format(meta["installed"]) in x:
                        continue
                    for y in x.splitlines():
                        if 'Depends: ' in y:
                            meta["kernel_abi"] = y.partition('pve-kernel-')[2]
                return meta
        return None

        for x in self._avail:
            pkg = x.partition(" - ")[0]
            self.available[pkg] = self.__get_kernel_details__(pkg)
            if loaded_krnl in pkg:
                self.available[pkg].active = True
                self.active = self.available[pkg]
            if self.available[pkg].installed:
                self.installed.append(pkg)


    def __get_available_kernels__(self):
        cmd = split('apt-cache search The Proxmox PVE Kernel Image')
        # pve-kernel-5.0.15-1-pve - The Proxmox PVE Kernel Image
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0 or \
           not ' - The Proxmox PVE Kernel Image' in res.stdout:
            return None
        res = list(res.stdout.splitlines())
        for x in res:
            if not " - The Proxmox PVE Kernel Image" in x:
                res.remove(x)
        return list(res)

    def __repr__(self):
        ret = {}
        ret["installed"] = self.installed
        ret["active"] = self.active
        ret["available"] = self.available
        ret["apt_updated"] = self.apt_updated
        return str(ret)

    def __str__(self):
        ret = "active: {}\n".format(self.active.pkg)
        ret = ret + "apt_updated: {}\n".format(self.apt_updated)
        ret = ret + "installed ({})\n".format(len(self.installed))
        for x in self.installed:
            if x == self.active.pkg:
                x = x + " [ACTIVE]"
            ret = ret + "    {}\n".format(x)
        ret = ret + "available ({})\n".format(len(self.available))
        for x in self.available:
            ret = ret + "    " + str(self.available[x]).replace('\n', '\n    ')
            ret = ret + "\n\n"
        return ret.rstrip()

    def __init__(self, update_apt = False):
        self.installed = []
        self.available = {}
        self.active = kernel()
        self.apt_updated = False
        if update_apt:
            cmd = split('apt-get update')
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0:
                self.apt_updated = True
            else:
                self.apt_updated = False
        self._avail = self.__get_available_kernels__()
        cmd = split('uname -r')
        loaded_krnl = subprocess.run(cmd, capture_output=True, text=True)
        loaded_krnl = loaded_krnl.stdout.strip()
        self.meta = self.__get_kernel_meta__()
        for x in self._avail:
            pkg = x.partition(" - ")[0]
            self.available[pkg] = self.__get_kernel_details__(pkg)
            if loaded_krnl in pkg:
                self.available[pkg].active = True
                self.active = self.available[pkg]
            if self.available[pkg].installed:
                self.installed.append(pkg)


def header(pp):
    pp.p("Script Version: {}".format(__VERSION))
    pp.p("Template Version: {}".format(__TEMPLATE_VERSION))
    pp.p("-------------------------------------------\n")

def get_template():
    subprocess.run(split('pveam update'))
    cmd = split('pveam available -section system')
    pp.dp("cmd: {}".format(cmd))
    res = subprocess.run(cmd, capture_output=True,
                         text=True).stdout.splitlines()
    _AVAIL = []
    for tmpl in res:
        tmpl = tmpl.rpartition(" ")[2].strip()
        if __TSEARCH in tmpl:
            _AVAIL.append(tmpl)
    if len(_AVAIL) == 0:
        sys.exit("Unable to get list of available system templates.")
    _AVAIL.sort(key=LooseVersion, reverse=True)
    pp.p("Downloading template: {}".format(_AVAIL[0]))
    cmd = split('pveam download local {}'.format(_AVAIL[0]))
    pp.dp("cmd: {}".format(cmd))
    res = subprocess.run(cmd, capture_output=True, text=True)
    pp.dp("res: {}".format(res))
    pp.dp("_AVAIL[0]: {}".format(_AVAIL[0]))

    cmd = split('pveam list local')
    pp.dp("cmd: {}".format(cmd))
    res = subprocess.run(cmd, capture_output=True,
                         text=True).stdout.splitlines()[1:]
    pp.dp("res: {}".format(res))
    _AVAIL={}
    for x in res:
        pp.dp("x: {}".format(x))
        if __TSEARCH in x:
            x = x.partition(" ")[0].partition(":")[2]
            pp.dp("x: {}".format(x))
            _AVAIL[x.partition("/")[2]] = x
            pp.dp("_AVAIL: {}\n".format(_AVAIL))
    pp.dp("_AVAIL Final: {}\n".format(_AVAIL))
    x = list(_AVAIL.keys())
    x.sort(key=LooseVersion, reverse=True)
    x = x[0]
    pp.dp("template: {}".format(x))
    pp.dp("template: {}".format(_AVAIL[x]))
    return {x: _AVAIL[x]}

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

    parser.add_argument("-V",
                        "--version",
                        help="Show version and exit",
                        action="store_true")

    parser.add_argument("-S",
                        "--share",
                        help="Path to shared folder",
                        type=str,
                        default="{}/shared".format(root_path))

    args = parser.parse_args()

    pp = prettyprint(args.verbose)

    header(pp)

    pp.dp(args)
    #pp.dp(args.bridge)
    #pp.dp(pp.supports_color())
    tmpl = get_template()
    pp.dp("tmpl: {}".format(tmpl))
    sys.exit()

