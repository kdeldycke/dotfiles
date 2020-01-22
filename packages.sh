#!/usr/bin/env bash
set -x

# Packages to install on all targets, useful on both servers and desktops like
# CLIs and system utils.
COMMON_SERVER_PACKAGES="
bash
bash-completion
colordiff
colortail
coreutils
dmg2img
fdupes
findutils
git
git-extras
gpg
graphviz
grc
htop
imagemagick
jq
jnettop
legit
neovim
optipng
p7zip
pdftk-java
pngcrush
recode
rename
shellcheck
testdisk
tree
unrar
wget
"

# List of Desktop packages available via Brew sources on
# macOS.
COMMON_DESKTOP_PACKAGES="
faac
flac
fontforge
id3v2
lame
shntool
x264
youtube-dl
"

# List of Desktop packages available via Brew Cask on macOS.
COMMON_BIN_PACKAGES="
electrum
gimp
prey
subsurface
"

# Python packages to install from PyPi on all targets.
PYTHON_PACKAGES="
pip
gmvault
httpie
jupyter
meta-package-manager
neovim
pgcli
pipenv
pipenv-pipes
pycodestyle
pydocstyle
pygments
pylint
pytest
pytest-cov
pytest-sugar
setuptools
tox
wheel
yapf
"
