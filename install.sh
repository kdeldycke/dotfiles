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
COMMON_PACKAGES="git git-extras legit jnettop hfsutils unrar subversion colordiff faac flac
lame x264 graphviz qemu lftp shntool testdisk fdupes recode pngcrush rtmpdump
optipng colortail mercurial grc coreutils bzr htop apg fontforge"

BIN_PACKAGES="audacity avidemux darktable firefox gimp inkscape vlc blender thunderbird
virtualbox wireshark prey inkscape"

# Install all software first.
if $IS_OSX; then
    source ./scripts/osx-install.sh
else
    source ./scripts/ubuntu-install.sh
fi

# Search local dotfiles
DOT_FILES=$(find . -maxdepth 1 \
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
    -exec basename {} \;)

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
        ln -sf "${source}" "$(dirname "${target}")"
    fi
done

# Create empty folders
mkdir -p ~/.pip/cache

# Configure everything.
if $IS_OSX; then
    source ./scripts/osx-config.sh
else
    source ./scripts/ubuntu-config.sh
fi

# Install & upgrade all global python modules
PYTHON_PACKAGES="pip setuptools virtualenv virtualenvwrapper autoenv pep8 pylint pyflakes
coverage rope autopep8 mccabe nose bumpversion tox"
for p in $PYTHON_PACKAGES
do
    sudo pip install --upgrade "$p"
done

# Patch terminal font for Vim's Airline plugin
# See: https://powerline.readthedocs.org/en/latest/fontpatching.html
mkdir ./powerline-fontpatcher
curl -fsSL https://github.com/Lokaltog/powerline-fontpatcher/tarball/develop | tar -xvz --strip-components 1 --directory ./powerline-fontpatcher -f -
fontforge -script ./powerline-fontpatcher/scripts/powerline-fontpatcher --no-rename ./assets/SourceCodePro-Regular.otf
rm -rf ./powerline-fontpatcher
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

# Force vim plugin upgrades
vim +NeoBundleUpdate +q

# Reload Bash with new configuration
source ~/.bash_profile
