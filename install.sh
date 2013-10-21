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
optipng colortail colorsvn mercurial grc coreutils"

BIN_PACKAGES="audacity avidemux firefox gimp inkscape vlc blender thunderbird virtualbox
bitcoin-qt wireshark prey"

# Define global Python packages
PYTHON_PACKAGES="readline pip setuptools distribute virtualenv virtualenvwrapper autoenv pep8
pylint pyflakes coverage rope autopep8 mccabe"

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
        # TODO: fix recursive symlinks
        ln -sf "${source}" "${target}"
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

# Reload Bash with new configuration
source ~/.bash_profile
