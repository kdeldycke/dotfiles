#!/usr/bin/env bash
set -x

# Packages to install on all targets, useful on both servers and desktops like
# CLIs and system utils.
COMMON_SERVER_PACKAGES="
apg
bash
bash-completion
colordiff
colortail
coreutils
fdupes
findutils
git
git-extras
gpg
graphviz
grc
hfsutils
htop
imagemagick
jq
jnettop
legit
mercurial
neovim
optipng
p7zip
pgcli
pngcrush
recode
rename
rtmpdump
shellcheck
testdisk
tree
unrar
wget
"

# Packages to install on both Ubuntu and Kubuntu, desktops and servers, but not
# macOS.
UBUNTU_SERVER_PACKAGES="
apt-file
ca-certificates
cpufrequtils
deborphan
hfsplus
hfsprogs
libimage-exiftool-perl
lm-sensors
mbr
ntfs-3g
ntp
p7zip-full
powertop
psmisc
sysfsutils
system-config-lvm
xfsprogs
xsltproc
zfs-dkms
zfsutils-linux
"

# List of Desktop packages available via apt on Ubuntu and Brew sources on
# macOS.
COMMON_DESKTOP_PACKAGES="
faac
flac
fontforge
id3v2
lame
shntool
wireshark
x264
youtube-dl
"

# List of Desktop packages available via apt on Ubuntu and Brew Cask on macOS.
COMMON_BIN_PACKAGES="
audacity
firefox
gimp
handbrake
hugin
inkscape
prey
sqlitebrowser
subsurface
virtualbox
"

# Packages to install on Kubuntu desktops only.
KUBUNTU_DESKTOP_PACKAGES="
bitcoin-qt
bleachbit
chromium-browser
chromium-codecs-ffmpeg-extra
dmg2img
driftnet
dupeguru-se
efibootmgr
exfat-fuse
exfat-utils
faad
gimp-plugin-registry
gitg
hunspell-fr
hunspell-fr-classical
kdenlive
kompare
kwrite
libavcodec-extra
libdvd-pkg
mkvtoolnix
mkvtoolnix-gui
mpv
network-manager-openvpn
pdftk
picard
transcode
ttf-ancient-fonts
unclutter
"

# Python packages to install from PyPi on all targets.
PYTHON_PACKAGES="
pip
bumpversion
coverage
flake8
gmvault
gsutil
httpie
jupyter
meta-package-manager
neovim
nose
nose-progressive
pycodestyle
pydocstyle
pygments
pylint
setuptools
tox
virtualenv
virtualenvwrapper
wheel
yapf
"
