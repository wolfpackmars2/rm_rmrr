#!/usr/bin/env python3
#==============================================================================
# vim: softtabstop=4 shiftwidth=4 expandtab fenc=utf-8 cc=80 nu
#==============================================================================
import argparse, multiprocessing, os, sys, subprocess, pdb
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

class lxc:

    def __repr__(self):
        return str(self.__dict__)

    def __str__(self):
        ret = ""
        d = self.__dict__
        maxl = len(max(d.keys())) + 4
        for x in d:
            ret = ret + "{}: {}\n".format(str(x).rjust(maxl), str(d[x]))
        return ret.strip()

    def __init__(self, lxc_id=500, shared_dir="shared", cores=None, ram=None,
                 bridge_id=0, template="debian-10", storage="local-lvm"):
        self.id = lxc_id
        self.shared_dir = os.path.abspath(shared_dir)
        self.cores = cores
        self.ram = ram
        if self.cores is None:
            c = multiprocessing.cpu_count()
            if c > 10:
                self.cores = c - 4
            elif c > 2:
                self.cores = c - 2
            else:
                self.cores = c
        if self.ram is None:
            cmd = split('free -t -m')
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0:
                r = int(res.stdout.splitlines()[-1].split()[3]) // 1024
            else:
                r = 4
            if r > 8:
                self.ram = 6
                if self.cores > 80:
                    self.cores = 80 #6GiB tested with up to 80 cores
            else:
                self.ram = 4
                if self.cores > 10:
                    self.cores = 8 #limit cores due to low ram
        self.bridge_id = bridge_id
        #pp.dp("lxc: {}".format(str(self.__dict__)))

def sp_run(cmd, capture_output=True, timeout=None,
        check=False, encoding=None, text=True, **kwargs):
    if type(cmd) is str:
        cmd = split(cmd)
    pp.dp("cmd: {}".format(cmd))
    return subprocess.run(cmd, capture_output=capture_output,
                          timeout=timeout, check=check, encoding=encoding,
                          text=text, **kwargs)

def header(pp):
    pp.p("Script Version: {}".format(__VERSION))
    pp.p("Template Version: {}".format(__TEMPLATE_VERSION))
    pp.p("-------------------------------------------\n")

def get_template(name='debian-10', update=False, storage=None):
    pp.dp("get_template.name: {}".format(name))
    pp.dp("get_template.update: {}".format(update))
    pp.dp("get_template.storage: {}".format(storage))
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
        pp.dp("cmd: {}".format(cmd))
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
    _AVAIL=[]
    for x in res:
        pp.dp("x: {}".format(x))
        if __TSEARCH in x:
            x = x.split()[0]
            pp.dp("x: {}".format(x))
            #_AVAIL[x.partition("/")[2]] = x
            _AVAIL.append(x)
            pp.dp("_AVAIL: {}\n".format(_AVAIL))
    pp.dp("_AVAIL Final: {}\n".format(_AVAIL))
    _AVAIL.sort(key=LooseVersion, reverse=True)
    pp.dp("template: {}".format(_AVAIL[0]))
    return _AVAIL[0]

def write_bootstrap_scripts():
    script=("#!/bin/sh -\n"
            "if ! [ \"$(id -u)\" -eq 0 ]; then\n"
            "    echo Must be root" + "\n"
            "    exit 1" + "\n"
            "fi" + "\n"
            "workdir=$(pwd -P)" + "\n"
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
            "\n" + "if ! [ -d \"${workdir}/build\" ]; then"
            "\n" + "    mkdir -p \"${workdir}/build\""
            "\n" + "fi"
            "\n" + "cd \"${workdir}/build\""
            #"\n" + "if ! [ -d \"kernel\" ]; then (mkdir \"kernel\"); fi"
            #"\n" + "cd kernel"
            "\n" + "git clone git://git.proxmox.com/git/pve-kernel.git"
            "\n" + ""
            "\n" + ""
            "\n" + ""
            "\n" + "")
    pdb.set_trace()
    pp.dp("script: {}".format(script))
    return script

def create_lxc(cont, tmpl, storage='local-lvm'):
    pp.dp("f: create_lxc")
    cmd = ("pct create {id} \"{tmpl}\" -storage {storage} -memory {ram} "
           "-net0 \"name=eth0,bridge=vmbr{bridge},hwaddr=FA:4D:70:91:B8:6F,"
           "ip=dhcp,type=veth\" -hostname buildr -cores {cores} -rootfs 80 "
           "-mp0 \"{share},mp=/root/shared,ro=0\"")
    cmd = cmd.format(id = cont.id,
                     tmpl = tmpl,
                     storage = storage,
                     ram = cont.ram * 1024,
                     bridge = cont.bridge_id,
                     cores = cont.cores,
                     share = cont.shared_dir)
    #cmd = cmd.format(id=cont.id, tmpl=tmpl, storage=storage, ram=cont.ram,
    #                 bridge=cont.bridge_id, cores=cont.cores,
    #                 share=cont.shared_dir)
    if os.path.exists(cont.shared_dir):
        #shared_dir object already exists. is it a directory?
        if not os.path.isdir(cont.shared_dir):
            # shared_dir object exists but is not a directory. stop
            return False
        # shared directory exists, overwrite?
    else:
        #shared_dir doesn't exist, create it
        os.makedirs(cont.shared_dir)
    pp.dp("cmd: {}".format(cmd))
    cmd = split(cmd)
    pp.dp("cmd: {}".format(cmd))
    pp.p("Created LXC {}".format(cont.id))
    #pdb.set_trace()
    res = sp_run(cmd)
    if res.returncode == 0:
        pp.dp("LXC Create result: {}".format(res.stdout))
        return True
    pp.dp("LXC Create error: {}".format(res.stderr))
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
    cont = lxc(lxc_id=args.id, shared_dir=args.share)
    pp.dp("cont: {}".format(cont))
    if create_lxc(cont, tmpl):
        cmd = split('pct start {}'.format(cont.id))
        res = sp_run(cmd)
        pp.dp("cmd output: {}".format(res))
    script = write_bootstrap_scripts()
    with open(cont.shared_dir + '/bootstrap.sh', "w") as script_file:
        script_file.write(script)
    # a file exists in the pve kernel package which specifies the git id
    # the package was built against
    # next step is to figure out which build was used and git checkout
    # that build.
    # after that, determine which sub-projects to download
    # after that, determine which packages still need to be installed
    # after that, make! profit :)
    sys.exit()

