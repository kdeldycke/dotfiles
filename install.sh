#!/usr/bin/env bash
set -x

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
    # Link files
    if [ -e "${TARGET}" ] && [ ! -L "${TARGET}" ]; then
        mv "$TARGET" "$TARGET.dotfiles.bak"
    fi
    ln -sf "${SOURCE}" "$(dirname "${TARGET}")"
done

# Load package lists to install.
source ./packages.sh

# Install all software first.
if $IS_MACOS; then
    source ./scripts/macos-install.sh
    source ./scripts/macos-install-refind.sh
else
    source ./scripts/ubuntu-server-install.sh
    if $IS_DESKTOP; then
        source ./scripts/kubuntu-desktop-install.sh
    fi
fi

# Install & upgrade all global python modules
for p in $PYTHON_PACKAGES
do
    pip install --upgrade "$p"
done

# Patch terminal font on desktops for Vim's Airline plugin.
# See: https://powerline.readthedocs.org/en/latest/fontpatching.html
if $IS_DESKTOP; then
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
fi

# Force Neovim plugin upgrades
nvim -c "try | call dein#update() | finally | qall! | endtry"

# Configure everything.
if $IS_MACOS; then
    source ./scripts/macos-config.sh
else
    source ./scripts/ubuntu-server-config.sh
    if $IS_DESKTOP; then
        source ./scripts/kubuntu-desktop-config.sh
    fi
fi

# Reload Bash with new configuration
source ~/.bash_profile
