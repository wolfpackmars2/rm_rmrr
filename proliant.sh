#!/bin/sh -
# requires min. 4GiB RAM, CPU Cores >= 4
# recommend 16GiB RAM or greater, Quad Core CPU with HT or better
_VAGRANT_VM_CORES=`grep -c ^processor /proc/cpuinfo`
_VAGRANT_VM_CORES=`expr $_VAGRANT_VM_CORES - 2`
_VAGRANT_VM_NAME="HPRMRRPATCH"
_VAGRANT_VM_BOX="ubuntu/bionic64"
_VAGRANTFILE_DIR="`pwd`"

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
    cat > "${_VAGRANTFILE_DIR}/vagrant_bootstrap.sh" <<- EOM
#!/bin/sh -
cd /root
echo "==== BEGIN YARN SETUP ====================================="
curl -sS https://dl.yarnpkg.com/debian/pubkey.gpg | apt-key add -
echo "deb https://dl.yarnpkg.com/debian/ stable main" > "/etc/apt/sources.list.d/yarn.list"
echo "==== END YARN SETUP ====================================="
apt update
DEBIAN_FRONTEND=noninteractive apt upgrade -y
echo "==== BEGIN ADD RUBY REPO ====================================="
apt-add-repository ppa:brightbox/ruby-ng -y
echo "==== END ADD RUBY REPO ====================================="
pkgs="build-essential"
pkgs="ruby2.5 \${pkgs}"
pkgs="ruby2.5-dev \${pkgs}"
pkgs="zip \${pkgs}"
pkgs="libxslt-dev \${pkgs}"
pkgs="libxml2-dev \${pkgs}"
pkgs="libpq-dev \${pkgs}"
pkgs="yarn \${pkgs}"
pkgs="p7zip \${pkgs}"
pkgs="nginx \${pkgs}"
pkgs="openjdk-8-jdk \${pkgs}"
pkgs="postgresql-contrib \${pkgs}"
pkgs="postgresql \${pkgs}"
echo "==== BEGIN APT PACKAGE INSTALL ====================================="
DEBIAN_FRONTEND=noninteractive apt install -y \${pkgs}
echo "==== END APT PACKAGE INSTALL ====================================="
cd "${_GUESTFILES_DIR}"
echo "==== BEGIN GEM UPDATE ====================================="
gem update --system
echo "==== END GEM UPDATE ===== BEGIN BUNDLE INSTALL ========================="
if ! [ -e /usr/bin/bundle ]; then
    ln -s \`ls -r1 /usr/bin/bundle* | head -n 1 || ( echo "bundler not found && exit 1" )\` /usr/bin/bundle
fi
if ! [ -e /usr/bin/bundler ]; then
    ln -s \`ls -r1 /usr/bin/bundle* | head -n 1 || ( echo "bundler not found && exit 1" )\` /usr/bin/bundler
fi
su vagrant -c "bundle install --path vendor/bundler" || ( echo "Err 5099" && exit 1 )
echo "==== END BUNDLE INSTALL ====================================="
#/usr/lib/postgresql/10/bin/pg_ctl -D /var/lib/postgresql/10/main start
service postgresql start
sudo -u postgres psql -c "ALTER USER postgres PASSWORD 'password';"
echo "==== BEGIN POST INSTALL TASKS ====================================="
echo "cd \\"${_GUESTFILES_DIR}\\"" >> ~/.bashrc
mv /vagrant/certs.spartan-ecommerce_vagrant.crt \\
  /etc/ssl/certs/spartan-ecommerce_vagrant.crt || ( echo "Err 5100" && exit 1 )
chown root:root /etc/ssl/certs/spartan-ecommerce_vagrant.crt
mv /vagrant/private.spartan-ecommerce_vagrant.key \\
  /etc/ssl/private/spartan-ecommerce_vagrant.key || ( echo "Err 5102" && exit 1 )
chown root:ssl-cert /etc/ssl/private/spartan-ecommerce_vagrant.key || ( echo "Err 5103" && exit 1 )
search="local   all             postgres                                peer"
replace="local   all             postgres                                md5"
targetfile="/etc/postgresql/10/main/pg_hba.conf"
sed -i "s/\${search}/\${replace}/g" "\${targetfile}"
grep -q "\${replace}" "\${targetfile}" || ( echo "Err 5103 pgsql config failed" && exit 1 )
#sed -i 's/local   all             postgres                                peer/local   all             postgres                                md5/g' /etc/postgresql/10/main/pg_hba.conf
#echo "local   all             postgres                                md5" \\
#  >> /etc/postgresql/10/main/conf.d/50-devbootstrap.conf
service postgresql restart
mv /vagrant/sites-available.spartan-ecommerce_vagrant \\
  /etc/nginx/sites-available/spartan-ecommerce_vagrant
chown vagrant:vagrant /etc/nginx/sites-available/spartan-ecommerce_vagrant
ln -s /etc/nginx/sites-available/spartan-ecommerce_vagrant \\
  /etc/nginx/sites-enabled/spartan-ecommerce_vagrant
cd "${_GUESTFILES_DIR}"
# remove existing solr directory
if [ -d ./solr ]; then
  rm -rf solr
fi
echo "==== RUNNING RAKE TASKS ========================================="
echo " >> rake db:setup"
bin/rake db:setup || echo "rake db:setup failed"
echo " >> rake sunspot:solr:start"
bin/rake sunspot:solr:start || echo "rake sunspot:solr:start failed"
echo " >> rake import:macpac:all"
bin/rake import:macpac:all || echo "rake import:all failed"
echo " >> rake sunspot:reindex"
bin/rake sunspot:reindex || echo "rake sunspot:reindex failed"
echo "==== END POST INSTALL TASKS ====================================="
exit 0

EOM
}

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#         NAME:  mk_bootstrap_script
#  DESCRIPTION:  Creates script to bootstrap the vagrant VM
#----------------------------------------------------------------------------------------------------------------------
mk_bootstrap_script()
{
    cat > "${_VAGRANTFILE_DIR}/vagrant_bootstrap.sh" <<- EOM
#!/bin/sh -
cd /root
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
mv mirror_ubuntu-disco-kernel ubuntu-disco
echo "==== BEGIN POST INSTALL TASKS ====================================="
search="local   all             postgres                                peer"
replace="local   all             postgres                                md5"
targetfile="/etc/postgresql/10/main/pg_hba.conf"
#sed -i "s/\${search}/\${replace}/g" "\${targetfile}"
#grep -q "\${replace}" "\${targetfile}" || ( echo "Err 5103 pgsql config failed" && exit 1 )
echo "==== RUNNING RAKE TASKS ========================================="
echo "==== END POST INSTALL TASKS ====================================="
exit 0

EOM
}

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __detect_color_support
#   DESCRIPTION:  Try to detect color support.
#----------------------------------------------------------------------------------------------------------------------
__detect_color_support() {
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
        if ! [ vagrant box add "${_VAGRANT_VM_BOX}" ]; then
            echoerror "Unable to load vagrant box ${_VAGRANT_VM_BOX}. Cannot continue."
            exit 1
        fi
    else
        if ! (vagrant box update --box "${_VAGRANT_VM_BOX}"); then
            echowarn "Unable to update vagrant box ${_VAGRANT_VM_BOX}. Continuing without update..."
        fi
    fi
}

#----------------------------------------------------------------------------------------------------------------------
#  DESCRIPTION:  Run sanity checks
#----------------------------------------------------------------------------------------------------------------------
if ! __check_command_exists vagrant; then
    echo
    echoerror "vagrant missing. Install vagrant from https://vagrantup.com"
    echo
    exit 1
fi
if ! __check_command_exists virtualbox; then
    echo
    echoerror "virtualbox missing. Install virtualbox from https://www.virtualbox.com"
    echo
    exit 1
fi

#---  MAIN  -----------------------------------------------------------------------------------------------------------
#  DESCRIPTION:  Start main program
#----------------------------------------------------------------------------------------------------------------------
__detect_color_support
getram
echo $_VAGRANT_VM_RAM
echo $_VAGRANT_VM_CORES
echo ${_VAGRANTFILE_DIR}
vagrant_box
mk_vagrantfile
mk_bootstrap_script
vagrant up || ( echoerror "vagrant up failed" && exit 1 )
vcmd="sudo sh /vagrant/vagrant_bootstrap.sh"
echo "${vcmd}"
vagrant ssh "${_VAGRANT_VM_NAME}" -- -q -t "${vcmd}" || echo "Vagrant command failed"

