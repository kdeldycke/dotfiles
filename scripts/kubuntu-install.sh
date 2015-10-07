#!/usr/bin/env bash -x

sudo apt-get update
sudo apt-get install -y aptitude apt-transport-https software-properties-common

sudo add-apt-repository -y ppa:sunab/kdenlive-release
sudo add-apt-repository -y ppa:bitcoin/bitcoin
sudo add-apt-repository -y ppa:subsurface/subsurface
sudo add-apt-repository -y ppa:micahflee/ppa

# Install tox repositories.
# Source: https://wiki.tox.chat/binaries#debian_ubuntu_mint_etc
echo "deb https://pkg.tox.chat/debian nightly release" | sudo tee /etc/apt/sources.list.d/tox.list
wget -qO - https://pkg.tox.chat/debian/pkg.gpg.key | sudo apt-key add -

sudo aptitude update
sudo aptitude upgrade -y


# Install common packages
for p in $COMMON_PACKAGES
do
    sudo aptitude install -y "$p"
done
for p in $BIN_PACKAGES
do
    sudo aptitude install -y "$p"
done

# Install Ubuntu specific packages
sudo aptitude install -y ack-grep aegisub apt-file avidemux-common \
bitcoin-qt bleachbit ca-certificates chromium-browser \
chromium-codecs-ffmpeg-extra cpufrequtils deborphan dmg2img driftnet efibootmgr \
exfat-fuse exfat-utils faad gimp-plugin-registry gitg \
hfsplus hfsprogs hunspell-fr hunspell-fr-classical kdenlive kdesdk-scripts \
kompare kscreensaver kwrite libavcodec-extra libimage-exiftool-perl lm-sensors mbr \
mkvtoolnix mkvtoolnix-gui mplayer2 network-manager-openvpn ntp p7zip-full picard \
powertop psmisc sqlitebrowser sysfsutils system-config-lvm transcode ttf-ancient-fonts \
unclutter utox vim-nox xfsprogs xscreensaver xscreensaver-data \
xscreensaver-data-extra xscreensaver-gl xscreensaver-gl-extra xsltproc


sudo aptitude install -y python-pip python-dev runsnakerun


sudo aptitude install -y libpq-dev
pip install --upgrade pgcli


sudo aptitude install -y virt-manager
sudo usermod -a -G libvirtd kevin
sudo usermod -a -G kvm kevin


sudo aptitude install -y redshift gtk-redshift geoclue


# Install libCSS to decode encrypted DVDs
sudo /usr/share/doc/libdvdread4/install-css.sh


# Install cabal and shellcheck
sudo aptitude install -y cabal-install
cabal update
cabal install shellcheck


# Install GMVault
pip install --allow-external IMAPClient --upgrade https://pypi.python.org/packages/source/g/gmvault/gmvault-1.8.1-beta.tar.gz#md5=a0b26d814506748deca8e2eee4086b31


# Install Pelican and its dependencies
sudo aptitude install -y python-markdown python-pygments python-beautifulsoup pandoc \
python-smartypants s3cmd
pip install --upgrade pelican mdx_video typogrify Fabric


# Install Dropbox if not already there
[ ! -f ~/.dropbox-dist/dropbox ] && wget -O - "http://www.dropbox.com/download?plat=lnx.x86_64" | tar -xvz --directory ~ -f -


# Install google music manager
wget "https://dl.google.com/linux/direct/google-musicmanager-beta_current_amd64.deb"
sudo dpkg -i ./google-musicmanager-beta_current_amd64.deb
rm ./google-musicmanager-beta_current_amd64.deb


# Install insync
wget -qO - https://d2t3ff60b2tol4.cloudfront.net/services@insynchq.com.gpg.key | sudo apt-key add -
sudo tee /etc/apt/sources.list.d/insync-vivid.list <<-EOF
    deb http://apt.insynchq.com/ubuntu vivid non-free contrib
EOF
sudo aptitude update
sudo aptitude install -y insync insync-dolphin


# Install Steam
sudo dpkg --add-architecture i386
sudo aptitude update
sudo aptitude install -y steam mesa-utils


# Install Tor Browser.
sudo aptitude install -y torbrowser-launcher
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
wget -O - "http://178.62.189.137/build/Popcorn-Time-0.3.8-0-Linux-64.tar.xz" | tar -xvJ --directory ~/Popcorn-Time -f -
[ ! -f /lib/x86_64-linux-gnu/libudev.so.0 ] && sudo ln -s /lib/x86_64-linux-gnu/libudev.so.1 /lib/x86_64-linux-gnu/libudev.so.0


# Remove all unused default KDE apps.
sudo aptitude remove -y akregator kaddressbook knotes kontact korganizer dragonplayer kamera kcalc \
kaccessible kdegraphics-strigi-analyzer kmag kpat rekonq quassel kmail unity-gtk2-module \
unity-gtk3-module kde-telepathy telepathy-logger telepathy-indicator telepathy-salut \
kde-config-telepathy-accounts kde-telepathy-approver kde-telepathy-data telepathy-gabble \
libtelepathy-logger3 libtelepathy-glib0 libtelepathy-qt4-2 amarok amarok-utils amarok-common \
akonadi-backend-mysql akonadi-server apturl-kde kdepim-kresources kdepim-runtime libcalendarsupport4 \
libincidenceeditorsng4 libkdepim4 libkdepimdbusinterfaces4 libkleo4 libmailcommon4 libmailimporter4 \
libmessagecomposer4 libmessagecore4 libmessageviewer4 libpimcommon4 libtemplateparser4 \
python3-pykde4 mysql-server-core-5.6 mysql-common mysql-client-core-5.6 libmysqlclient18 \
libqt4-sql-mysql konversation konversation-data khelpcenter kde-telepathy-legacy-presence-applet \
libakonadiprotocolinternals1 baloo-utils libakonadi-kde4 libakonadi-kmime4 baloo-kf5 libbaloopim4

# Remove unused default system apps.
sudo aptitude remove -y nano kubuntu-web-shortcuts

# Remove Canonical crash reporters.
sudo aptitude remove -y apport apport-kde apport-symptoms kde-config-whoopsie python3-apport whoopsie

sudo apt-file update

sudo deborphan | xargs sudo apt-get -y remove --purge
sudo apt-get -y autoremove

# Clean the whole system based on preset.
sudo bleachbit --clean --preset
