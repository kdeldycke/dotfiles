#!/usr/bin/env bash
set -x

# Install command line tools
xcode-select -p
if [[ $? -ne 0 ]]; then
    xcode-select --install
fi

# A full installation of Xcode.app is required to compile some formulas like
# macvim. Installing the Command Line Tools only is not enough.
# Also, if Xcode is installed but the license is not accepted then brew will
# fail.
xcodebuild -version
# Accept Xcode license
if [[ $? -ne 0 ]]; then
    # TODO: find a way to install Xcode.app automatticaly
    # See: http://stackoverflow.com/a/18244349
    sudo xcodebuild -license
fi

# Update all OSX packages
sudo softwareupdate -i -a

# Install Homebrew if not found
brew --version 2>&1 >/dev/null
if [[ $? -ne 0 ]]; then
    # Clean-up failed Homebrew install
    ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/uninstall)"
    # Install Homebrew
    ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"
fi
brew update
brew upgrade --all

# Include duplicates packages
brew tap homebrew/dupes

# Install or upgrade Cask
brew tap caskroom/cask

# Install OSX system requirements
brew cask install --force xquartz

# Install a brand new Python
brew install python
brew link --overwrite python
# Install python 3 too.
brew install python3

# Install common packages
brew install apple-gcc42
for PACKAGE in $COMMON_PACKAGES
do
   brew install "$PACKAGE"
done
brew install ack
brew install cassandra
brew install dockutil
brew install exiftool
brew install faad2
brew install md5sha1sum
brew install osxutils
brew install pstree
brew install ssh-copy-id
brew install watch
brew install webkit2png

# htop-osx requires root privileges to correctly display all running processes.
sudo chown root:wheel "$(brew --prefix)/bin/htop"
sudo chmod u+s "$(brew --prefix)/bin/htop"

# Install binary apps
for PACKAGE in $BIN_PACKAGES
do
   brew cask install --force "$PACKAGE"
done
brew cask install --force aerial
brew cask install --force bitcoin-core
brew cask install --force chromium
brew cask install --force dropbox
brew cask install --force flux
brew cask install --force gitup
brew cask install --force insync
brew cask install --force libreoffice
brew cask install --force spectacle
brew cask install --force steam
brew cask install --force torbrowser
brew cask install --force transmission
brew cask install --force tunnelblick

# Install QuickLooks plugins
# Source: https://github.com/sindresorhus/quick-look-plugins
brew cask install --force betterzipql
brew cask install --force cert-quicklook
brew cask install --force epubquicklook
brew cask install --force java
brew cask install --force qlcolorcode
brew cask install --force qlmarkdown
brew cask install --force qlprettypatch
brew cask install --force qlstephen
brew cask install --force quicklook-csv
brew cask install --force quicklook-json
brew cask install --force suspicious-package
brew cask install --force webpquicklook
qlmanage -r

# Install GNU `sed`, overwriting the built-in `sed`.
brew install gnu-sed --with-default-names

# Install more recent versions of some OS X tools.
brew install homebrew/dupes/grep
brew install homebrew/dupes/openssh

# Add EXT support
brew cask install --force osxfuse
brew install homebrew/fuse/ext2fuse
brew install homebrew/fuse/ext4fuse

# Install vim
brew install lua --completion
brew install cscope
VIM_FLAGS="--with-python --with-lua --with-cscope --override-system-vim"
#brew install macvim "$VIM_FLAGS"
# Always reinstall vim to fix Python links.
# See: https://github.com/yyuu/pyenv/issues/234
brew reinstall vim "$VIM_FLAGS"

# Use sha256sum from coreutils
sudo ln -s /usr/local/bin/gsha256sum /usr/local/bin/sha256sum

# Install runsnakeerun
brew install wxmac
brew install wxpython
pip install --upgrade RunSnakeRun

# Install pgcli
brew install pgcli

# Install uBlock for Safari.
defaults read ~/Library/Safari/Extensions/extensions | grep --quiet "net.gorhill.uBlock"
if [[ $? -ne 0 ]]; then
    curl -o "$TMPDIR/ublock-safari.safariextz" -O https://cloud.delosent.com/ublock-safari-0.9.5.2.safariextz
    open "$TMPDIR/ublock-safari.safariextz"
fi

# Set chromium as the default browser.
brew install duti
duti -s org.chromium.Chromium http

# Clean things up
brew linkapps
brew cleanup
brew prune
brew cask cleanup
