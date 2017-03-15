#!/usr/bin/env bash
set -x

# We need to distinguish sources and binary packages for Brew & Cask on macOS
COMMON_PACKAGES="
apg
bash
bash-completion
colordiff
colortail
coreutils
faac
fdupes
findutils
flac
fontforge
git
git-extras
gpg
graphviz
grc
hfsutils
htop
id3v2
imagemagick
jq
jnettop
lame
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
shntool
testdisk
tree
unrar
wget
wireshark
x264
youtube-dl
"

BIN_PACKAGES="
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

# Detect platform.
if [ "$(uname -s)" == "Darwin" ]; then
    IS_MACOS=true
else
    IS_MACOS=false
fi

# Detect if Linux system is either a Plasma/KDE desktop or headless server.
IS_DESKTOP=true
if ! $IS_MACOS; then
    # Good candidates of installed packages hinting at a desktop are:
    # kde-baseapps, kde-runtime, plasma-desktop, plasma-framework,
    # plasma-workspace, xorg and xserver-common.
    # Among those, I choosed plasma-desktop as it is more generic than
    # Kubuntu-specifi packages. And removing the plasma-desktop package is
    # going to make your system unusable.
    apt list --installed --quiet | grep --quiet "^plasma-desktop"
    if [[ $? -ne 0 ]]; then
        IS_DESKTOP=false
    fi
fi

# Ask for the administrator password upfront.
sudo -v

# Keep-alive: update existing `sudo` time stamp until script has finished.
while true; do sudo -n true; sleep 60; kill -0 "$$" || exit; done 2>/dev/null &

# TODO: install git here.

# Force initialization and update of local submodules.
git submodule init
git submodule update --remote --merge

# Search local dotfiles
if $IS_MACOS; then
    DOT_FILES=$(find ./dotfiles-common ./dotfiles-macos -maxdepth 1 \
        -not -path "./dotfiles-common" \
        -not -path "./dotfiles-macos" \
        -not -name "\.DS_Store" -and \
        -not -name "*\.swp" -and \
        -not -name "*~*" )
else
    DOT_FILES=$(find ./dotfiles-common ./dotfiles-linux -maxdepth 1 \
        -not -path "./dotfiles-common" \
        -not -path "./dotfiles-linux" \
        -not -name "\.DS_Store" -and \
        -not -name "*\.swp" -and \
        -not -name "*~*" )
fi

for FILEPATH in $DOT_FILES
do
    SOURCE="${PWD}/$FILEPATH"
    TARGET="${HOME}/$(basename "${FILEPATH}")"
    if [ "$1" = "restore" ]; then
        # Restore backups if found
        if [ -e "${TARGET}.dotfiles.bak" ] && [ -L "${TARGET}" ]; then
            unlink "${TARGET}"
            mv "$TARGET.dotfiles.bak" "$TARGET"
        fi
    else
        # Link files
        if [ -e "${TARGET}" ] && [ ! -L "${TARGET}" ]; then
            mv "$TARGET" "$TARGET.dotfiles.bak"
        fi
        ln -sf "${SOURCE}" "$(dirname "${TARGET}")"
    fi
done

# Install all software first.
if $IS_MACOS; then
    source ./scripts/macos-install.sh
    source ./scripts/macos-install-refind.sh
else
    source ./scripts/kubuntu-install.sh
fi

# Install & upgrade all global python modules
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
for p in $PYTHON_PACKAGES
do
    pip install --upgrade "$p"
done

# Patch terminal font for Vim's Airline plugin
# See: https://powerline.readthedocs.org/en/latest/fontpatching.html
mkdir ./powerline-fontpatcher
curl -fsSL https://github.com/Lokaltog/powerline-fontpatcher/tarball/develop | tar -xvz --strip-components 1 --directory ./powerline-fontpatcher -f -
fontforge -script ./powerline-fontpatcher/scripts/powerline-fontpatcher --no-rename ./assets/SourceCodePro-Regular.otf
rm -rf ./powerline-fontpatcher
# Install the patched font
if $IS_MACOS; then
    mkdir -p ~/Library/Fonts/
    mv ./Source\ Code\ Pro.otf ~/Library/Fonts/
else
    mkdir -p ~/.fonts/
    mv ./Source\ Code\ Pro.otf ~/.fonts/
    # Refresh font cache
    sudo fc-cache -f -v
fi

# Force Neovim plugin upgrades
nvim -c ':call dein#update()'

# Configure everything.
if $IS_MACOS; then
    source ./scripts/macos-config.sh
else
    source ./scripts/kubuntu-config.sh
fi

# Reload Bash with new configuration
source ~/.bash_profile
