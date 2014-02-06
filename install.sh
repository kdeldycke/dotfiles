#!/usr/bin/env bash

# Detect distribution
if [ "$(uname -s)" == "Darwin" ]; then
    IS_OSX=true
else
    IS_OSX=false
fi

# Ask for the administrator password upfront
sudo -v
# Keep-alive: update existing `sudo` time stamp until script has finished
while true; do sudo -n true; sleep 60; kill -0 "$$" || exit; done 2>/dev/null &

# We need to distinguish sources and binary packages for Brew & Cask on OSX
COMMON_PACKAGES="git git-extras legit jnettop hfsutils unrar subversion ack colordiff faac flac
lame x264 inkscape graphviz qemu lftp shntool testdisk fdupes recode pngcrush exiftool rtmpdump
optipng colortail mercurial grc coreutils bzr htop apg fontforge"

BIN_PACKAGES="audacity avidemux firefox gimp inkscape vlc blender thunderbird virtualbox
bitcoin-qt wireshark prey"

# Search local dotfiles
DOT_FILES=`find . -maxdepth 1 \
    -not -name "assets" -and \
    -not -name "scripts" -and \
    -not -name "install.sh" -and \
    -not -name "\.DS_Store" -and \
    -not -name "\.gitignore" -and \
    -not -name "\.gitmodules" -and \
    -not -name "*\.dmg" -and \
    -not -name "*\.swp" -and \
    -not -name "*\.md" -and \
    -not -name "\.git" -and \
    -not -name "*~*" \
    -not -name "\." \
    -exec basename {} \;`

for f in $DOT_FILES
do
    source="${PWD}/$f"
    target="${HOME}/$f"
    if [ "$1" = "restore" ]; then
        # Restore backups if found
        if [ -e "${target}.dotfile.bak" ] && [ -L "${target}" ]; then
            unlink "${target}"
            mv "$target.dotfile.bak" "$target"
        fi
    else
        # Link files
        if [ -e "${target}" ] && [ ! -L "${target}" ]; then
            mv "$target" "$target.dotfile.bak"
        fi
        ln -sf "${source}" $(dirname "${target}")
    fi
done

# Create empty folders
mkdir -p ~/.pip/cache

# Call distribution specific scripts
if $IS_OSX; then
    source ./scripts/osx-install.sh
    source ./scripts/osx-config.sh
else
    source ./scripts/ubuntu-install.sh
    source ./scripts/ubuntu-config.sh
fi

# Install & upgrade all global python modules
PYTHON_PACKAGES="readline pip setuptools virtualenv virtualenvwrapper autoenv pep8 pylint pyflakes
coverage rope autopep8 mccabe nose"
sudo pip install --upgrade $PYTHON_PACKAGES

# Patch terminal font for Vim's Airline plugin
# See: https://powerline.readthedocs.org/en/latest/fontpatching.html
mkdir ./powerline-fontconfig
curl -fsSL https://github.com/Lokaltog/powerline/tarball/develop | tar -xvz --strip-components 2 --directory ./powerline-fontconfig -f -
fontforge -script ./powerline-fontconfig/fontpatcher.py --no-rename ./assets/SourceCodePro-Regular.otf
rm -rf ./powerline-fontconfig
# Install the patched font
if $IS_OSX; then
    mkdir -p ~/Library/Fonts/
    mv ./Source\ Code\ Pro.otf ~/Library/Fonts/
else
    mkdir -p ~/.fonts/
    mv ./Source\ Code\ Pro.otf ~/.fonts/
    # Refresh font cache
    sudo fc-cache -f -v
fi

# Reload Bash with new configuration
source ~/.bash_profile
