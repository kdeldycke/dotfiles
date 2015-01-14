#!/usr/bin/env bash

sudo apt-get update
sudo apt-get install -y aptitude

sudo add-apt-repository -y ppa:sunab/kdenlive-release
sudo add-apt-repository -y ppa:bitcoin/bitcoin
sudo add-apt-repository -y ppa:webupd8team/tor-browser

# Install tox repositories.
# Source: https://wiki.tox.im/Binaries#Apt.2FAptitude_.28Debian.2C_Ubuntu.2C_Mint.2C_etc..29
sudo sh -c 'echo "deb https://repo.tox.im/deb/ testing main" > /etc/apt/sources.list.d/toxrepo.list'
curl -k https://repo.tox.im/toxbuild.pgp | sudo apt-key add -

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
sudo aptitude install -y ack-grep aegisub apt-file audacious avidemux-common \
bitcoin-qt bleachbit bzrtools ca-certificates chromium-browser \
chromium-codecs-ffmpeg-extra cpufrequtils deborphan dmg2img driftnet efibootmgr \
exfat-fuse exfat-utils faad gimp-plugin-registry gitg gnome-themes-standard gtk-chtheme gtk2-engines \
hfsplus hfsprogs hunspell-fr hunspell-fr-classical kdenlive kdesdk-scripts \
kompare kscreensaver ksshaskpass kwrite libimage-exiftool-perl lm-sensors mbr \
mkvtoolnix mkvtoolnix-gui mplayer2 network-manager-openvpn ntp p7zip-full picard \
powertop qemu-kvm sqlitebrowser sysfsutils tor-browser transcode ttf-ancient-fonts \
unclutter utox vim-nox xfsprogs xscreensaver xscreensaver-data \
xscreensaver-data-extra xscreensaver-gl xscreensaver-gl-extra xsltproc


sudo aptitude install -y python-pip python-dev runsnakerun


sudo gem install hub


Sudo aptitude install -y libpq-dev
sudo pip install pgcli


sudo aptitude install -y virt-manager
sudo usermod -a -G libvirtd kevin
sudo usermod -a -G kvm kevin


sudo aptitude install -y redshift gtk-redshift geoclue


sudo aptitude install -y libavcodec-extra-53


# Install libCSS to decode encrypted DVDs
sudo /usr/share/doc/libdvdread4/install-css.sh


# Install cabal and shellcheck
sudo aptitude install -y cabal-install
cabal update
cabal install shellcheck


# Install GMVault
sudo pip install --allow-external IMAPClient --upgrade https://pypi.python.org/packages/source/g/gmvault/gmvault-1.8.1-beta.tar.gz#md5=a0b26d814506748deca8e2eee4086b31


# Install Pelican and its dependencies
sudo aptitude install -y python-markdown python-pygments python-beautifulsoup pandoc \
python-smartypants s3cmd
sudo pip install --upgrade pelican mdx_video typogrify Fabric


# Install Dropbox if not already there
[ ! -f ~/.dropbox-dist/dropbox ] && wget -O - "http://www.dropbox.com/download?plat=lnx.x86_64" | tar -xvz --directory ~ -f -


# Install google music manager
wget "https://dl.google.com/linux/direct/google-musicmanager-beta_current_amd64.deb"
sudo dpkg -i ./google-musicmanager-beta_current_amd64.deb
rm ./google-musicmanager-beta_current_amd64.deb


# Install insync
wget -qO - https://d2t3ff60b2tol4.cloudfront.net/services@insynchq.com.gpg.key | sudo apt-key add -
# TODO: don't add twice if config line already there
sudo tee -a /etc/apt/sources.list <<-EOF
    deb http://apt.insynchq.com/ubuntu saucy non-free contrib
EOF
sudo aptitude update
sudo aptitude install -y insync insync-dolphin


# Install Steam
sudo dpkg --add-architecture i386
sudo aptitude update
sudo aptitude install -y steam mesa-utils


# Install Popcorn Time
[ ! -d ~/Popcorn-Time ] && wget -O - "http://212.47.235.175/build/Popcorn-Time-0.3.6-Linux64.tar.xz" | tar -xvJ --directory ~ -f -
[ ! -f /lib/x86_64-linux-gnu/libudev.so.0 ] && sudo ln -s /lib/x86_64-linux-gnu/libudev.so.1 /lib/x86_64-linux-gnu/libudev.so.0


# Clean-up
sudo aptitude remove -y akregator kaddressbook knotes kontact korganizer dragonplayer kamera kcalc \
kaccessible kdegraphics-strigi-analyzer kmag kpat rekonq quassel kmail unity-gtk2-module \
unity-gtk3-module kde-telepathy telepathy-logger telepathy-indicator telepathy-salut \
kde-config-telepathy-accounts kde-telepathy-approver kde-telepathy-data telepathy-gabble \
libtelepathy-logger3 libtelepathy-glib0 libtelepathy-qt4-2

sudo apt-file update

sudo deborphan | xargs sudo apt-get -y remove --purge
sudo apt-get -y autoremove
