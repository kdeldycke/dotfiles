#!/usr/bin/env bash
set -x

# Detect platform.
if [ "$(uname -s)" != "Darwin" ]; then
    echo "These dotfiles only targets macOS."
    exit 1
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
DOT_FILES=$(find ./dotfiles-common ./dotfiles-macos -maxdepth 1 \
    -not -path "./dotfiles-common" \
    -not -path "./dotfiles-macos" \
    -not -name "\.DS_Store" -and \
    -not -name "*\.swp" -and \
    -not -name "*~*" )

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
source ./scripts/macos-install.sh
source ./scripts/macos-install-refind.sh

# Install & upgrade all global python modules
for p in $PYTHON_PACKAGES
do
    pip install --upgrade "$p"
done

# Patch terminal font on desktops for Vim's Airline plugin.
# See: https://powerline.readthedocs.org/en/latest/fontpatching.html
mkdir ./powerline-fontpatcher
curl -fsSL https://github.com/Lokaltog/powerline-fontpatcher/tarball/develop | tar -xvz --strip-components 1 --directory ./powerline-fontpatcher -f -
fontforge -script ./powerline-fontpatcher/scripts/powerline-fontpatcher --no-rename ./assets/SourceCodePro-Regular.otf
rm -rf ./powerline-fontpatcher
# Install the patched font
mkdir -p ~/Library/Fonts/
mv ./Source\ Code\ Pro.otf ~/Library/Fonts/

# Force Neovim plugin upgrades
nvim -c "try | call dein#update() | finally | qall! | endtry"

# Configure everything.
source ./scripts/macos-config.sh

# TODO: deduplicate bash history entries with:
# https://github.com/kdeldycke/scripts/blob/master/bash-history-merge.py

# Reload Bash with new configuration
source ~/.bash_profile
