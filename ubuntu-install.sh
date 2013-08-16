sudo apt-get update
sudo apt-get install aptitude

sudo add-apt-repository ppa:sunab/kdenlive-svn

sudo aptitude update
sudo aptitude upgrade



sudo aptitude install vim prey jnettop mkvtoolnix-gui mbr hfsutils hfsprogs hfsplus subtitlecomposer deborphan chromium-browser blender bzr kompare unrar avidemux-common transcode mkvtoolnix mencoder mplayer subversion git gitg bleachbit audacity gimp vlc p7zip-full firefox colordiff htop thunderbird virtualbox gtk-chtheme gnome-themes-standard python-pip faac faad flac h264enc lame kwrite kscreensaver x264 inkscape hunspell-fr hunspell-dictionary-fr aspell-fr gimp-plugin-registry xscreensaver xscreensaver-data xscreensaver-data-extra xscreensaver-gl xscreensaver-gl-extra network-manager-openvpn ksshaskpass bitcoin-qt graphviz qemu-kvm dmg2img pdftk lftp chromium-codecs-ffmpeg-extra picard xsltproc xfsprogs lm-sensors shntool bzrtools ntp ca-certificates testdisk fdupes apt-file recode pngcrush kdenlive python-dev gtk2-engines exiftool rtmpdump optipng runsnakerun



sudo aptitude install flashplugin-installer



sudo aptitude install virt-manager
sudo usermod -a -G libvirtd kevin
sudo usermod -a -G kvm kevin



sudo aptitude install redshift gtk-redshift geoclue



sudo aptitude install libavcodec-extra-53



# Install GMVault
sudo pip install --upgrade distribute
sudo pip install gmvault



# Install Pelican and its dependencies
sudo aptitude install python-markdown python-pygments python-beautifulsoup pandoc python-smartypants
sudo pip install pelican mdx_video typogrify



# Install Dropbox
cd ~ && wget -O - "http://www.dropbox.com/download?plat=lnx.x86_64" | tar xzf -



# Install google music manager
cd ~
wget "https://dl.google.com/linux/direct/google-musicmanager-beta_current_amd64.deb"
sudo dpkg -i ./google-musicmanager-beta_current_amd64.deb
rm ./google-musicmanager-beta_current_amd64.deb



# Install insync
wget -qO - https://d2t3ff60b2tol4.cloudfront.net/services@insynchq.com.gpg.key | sudo apt-key add -
sudo tee -a /etc/apt/sources.list <<-EOF
  deb http://apt.insynchq.com/ubuntu quantal non-free
EOF
sudo aptitude update
sudo aptitude install gir1.2-appindicator3-0.1 gir1.2-notify-0.7 insync-beta-kde
sudo ln -sf /usr/lib/x86_64-linux-gnu/libpython2.7.so.1 /usr/lib/libpython2.7.so.1
sudo ldconfig



sudo sed -i 's/GRUB_TIMEOUT=10/GRUB_TIMEOUT=1/g' /etc/default/grub
sudo update-grub



# It is highly recommended to use the fan controller daemon that is included in the mactel-support ppa called macfanctl.
# Source: http://download.maketecheasier.com/mba52/post-install-quantal.sh
# sudo add-apt-repository ppa:mactel-support/ppa
# sudo aptitude update
# sudo aptitude install macfanctld
# sudo service macfanctld stop
# sudo sed -i "s/\(^exclude:\).*\$/\\1 16 17 20/" /etc/macfanctl.conf
# sudo service macfanctld start

# sudo tee -a /etc/modprobe.d/hid_apple.conf <<-EOF
#   options hid_apple fnmode=2
# EOF
# sudo modprobe hid_apple

# wget -Nq http://pof.eslack.org/archives/files/mba42/00_usercustom || wget -Nq http://almostsure.com/mba42/00_usercustom
# sed -i "s/xxxxxxxx/$USER/" 00_usercustom
# chmod 0755 00_usercustom
# sudo mv 00_usercustom /etc/pm/sleep.d/00_usercustom
#
# wget -Nq http://pof.eslack.org/archives/files/mba42/dotXmodmap || wget -Nq http://www.almostsure.com/mba42/dotXmodmap
# mv dotXmodmap ~/.Xmodmap
# xmodmap ~/.Xmodmap

# TODO: test
# wget -Nq http://pof.eslack.org/archives/files/mba42/99_macbookair || wget -Nq http://www.almostsure.com/mba42/99_macbookair
# chmod 0755 99_macbookair
# sudo mv 99_macbookair /etc/pm/power.d/99_macbookair

# # --- re-enable hibernate
# # https://help.ubuntu.com/12.04/ubuntu-help/power-hibernate.html
# sudo tee /etc/polkit-1/localauthority/50-local.d/com.ubuntu.enable-hibernate.pkla <<-EOF
# [Re-enable hibernate by default]
# Identity=unix-user:*
# Action=org.freedesktop.upower.hibernate
# ResultActive=yes
# EOF
# gsettings set org.gnome.settings-daemon.plugins.power critical-battery-action 'hibernate'



sudo aptitude remove akregator kaddressbook knotes kontact korganizer dragonplayer kamera kcalc kaccessible kdegraphics-strigi-analyzer kdepim-strigi-plugins kmag kpat rekonq quassel kmail appmenu-gtk appmenu-gtk3

sudo apt-file update

deborphan | xargs apt-get -y remove --purge
