#!/usr/bin/env bash
set -x

sudo apt update
sudo apt install -y apt-transport-https software-properties-common

sudo add-apt-repository -y ppa:kdenlive/kdenlive-testing
sudo add-apt-repository -y ppa:bitcoin/bitcoin
sudo add-apt-repository -y ppa:subsurface/subsurface
sudo add-apt-repository -y ppa:micahflee/ppa
sudo add-apt-repository -y ppa:hsoft/ppa

sudo apt update
sudo apt upgrade -y


# Install common packages
for p in $COMMON_PACKAGES
do
    sudo apt install -y "$p"
done
for p in $BIN_PACKAGES
do
    sudo apt install -y "$p"
done

# Install Ubuntu specific packages
PACKAGES="
apt-file
bitcoin-qt
bleachbit
ca-certificates
chromium-browser
chromium-codecs-ffmpeg-extra
cpufrequtils
deborphan
dmg2img
driftnet
dupeguru-se
efibootmgr
exfat-fuse
exfat-utils
faad
gimp-plugin-registry
gitg
hfsplus
hfsprogs
hunspell-fr
hunspell-fr-classical
kdenlive
kdesdk-scripts
kompare
kwrite
libavcodec-extra
libdvd-pkg
libimage-exiftool-perl
lm-sensors
mbr
mkvtoolnix
mkvtoolnix-gui
network-manager-openvpn
ntfs-3g
ntp
p7zip-full
pdftk
picard
powertop
psmisc
sysfsutils
system-config-lvm
transcode
ttf-ancient-fonts
unclutter
vim-nox
xfsprogs
xsltproc
zfs-dkms
zfsutils-linux
"
# Install packages one by one for debug.
#for p in $PACKAGES
#do
#    sudo apt install -y "$p"
#done
sudo apt install -y $PACKAGES


sudo apt install -y python-pip python-dev runsnakerun


sudo apt install -y virt-manager
sudo usermod -a -G libvirtd kevin
sudo usermod -a -G kvm kevin


sudo apt install -y redshift gtk-redshift geoclue


# Install cabal and shellcheck
sudo apt install -y cabal-install
cabal update
cabal install shellcheck


# Install Dropbox if not already there
[ ! -f ~/.dropbox-dist/dropbox ] && wget -O - "https://www.dropbox.com/download?plat=lnx.x86_64" | tar -xvz --directory ~ -f -


# Install google music manager
wget -qO - https://dl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
wget -P /tmp "https://dl.google.com/linux/direct/google-musicmanager-beta_current_amd64.deb"
sudo apt install /tmp/google-musicmanager-beta_current_amd64.deb
rm /tmp/google-musicmanager-beta_current_amd64.deb


# Install insync
wget -qO - https://d2t3ff60b2tol4.cloudfront.net/services@insynchq.com.gpg.key | sudo apt-key add -
sudo tee /etc/apt/sources.list.d/insync-wily.list <<-EOF
    deb http://apt.insynchq.com/ubuntu wily non-free contrib
EOF
sudo apt update
sudo apt install -y insync insync-dolphin


# Install Steam
sudo dpkg --add-architecture i386
sudo apt update
sudo apt install -y steam mesa-utils


# Install Tor Browser.
sudo apt install -y torbrowser-launcher
torbrowser-launcher
# The launcher package above starts tor service by default to download the
# initial browser binary. See:
# https://github.com/micahflee/torbrowser-launcher/issues/188#issuecomment-114574424
# Deactive tor service once the browser is installed.
#sudo systemctl stop tor.service
#sudo systemctl disable tor.service
# Force installation of uBlock origin
wget https://addons.mozilla.org/firefox/downloads/file/319372/ -O \
    ~/.local/share/torbrowser/tbb/x86_64/tor-browser_en-US/Browser/TorBrowser/Data/Browser/profile.default/extensions/uBlock0@raymondhill.net.xpi


# Install Popcorn Time
rm -rf ~/Popcorn-Time
mkdir -p ~/Popcorn-Time
wget -O - "https://get.popcorntime.sh/build/Popcorn-Time-0.3.9-Linux-64.tar.xz" | tar -xvJ --directory ~/Popcorn-Time -f -


# Install local copy of wikipedia.
rm -rf ~/wikipedia
mkdir -p ~/wikipedia
wget -O - "https://download.kiwix.org/bin/kiwix-linux-x86_64.tar.bz2" | tar -xvj --directory ~/wikipedia -f -


# Remove all unused default KDE apps.
UNUSED_PACKAGES="
akregator
kaddressbook
knotes
kontact
korganizer
dragonplayer
kamera
kcalc
kaccessible
kdegraphics-strigi-analyzer
kmag
kpat
rekonq
quassel
kmail
krdc
unity-gtk2-module
unity-gtk3-module
kde-telepathy
telepathy-logger
telepathy-indicator
telepathy-salut
kde-telepathy-minimal
kde-config-telepathy-accounts
kde-telepathy-approver
kde-telepathy-auth-handler
kde-telepathy-contact-list
kde-telepathy-filetransfer-handler
kde-telepathy-integration-module
kde-telepathy-send-file
kde-telepathy-text-ui
kde-telepathy-data
kde-telepathy-desktop-applets
kde-telepathy-kpeople
qml-module-org-kde-telepathy
libktplogger9
libtelepathy-logger-qt5
libtelepathy-logger3
libktpotr9
libktpwidgets9
libktpmodels9
libktpcommoninternals9
telepathy-accounts-signon
telepathy-mission-control-5
libmission-control-plugins0
libtelepathy-glib0
libtelepathy-qt4-2
kde-telepathy-legacy-presence-applet
amarok-utils
amarok-common
amarok
accountwizard
akonadi-backend-mysql
akonadi-server
apturl-kde
kdepim-runtime
libkdepim4
libmessageviewer4
python3-pykde4
mysql-server-core-5.6
mysql-common
mysql-client-core-5.6
libmysqlclient18
libqt5sql5-mysql
libqt4-sql-mysql
konversation
konversation-data
khelpcenter
libakonadiprotocolinternals1
baloo-utils
libakonadi-kde4
libakonadi-kmime4
libbaloopim4
"
# Remove packages one by one for debug.
#for p in $UNUSED_PACKAGES
#do
#    sudo apt remove "$p"
#done
sudo apt remove -y $UNUSED_PACKAGES

# Remove unused default system apps.
sudo apt remove -y nano kubuntu-web-shortcuts

# Remove Canonical crash reporters.
sudo apt remove -y apport apport-kde apport-symptoms kde-config-whoopsie python3-apport whoopsie whoopsie-preferences libwhoopsie-preferences0

sudo apt-file update

sudo deborphan | xargs sudo apt -y remove --purge
sudo apt -y autoremove

# Clean the whole system based on preset.
sudo bleachbit --clean --preset
