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
brew cask install xquartz

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
brew install avidemux
brew install cassandra
brew install curl
brew link --force curl
brew install dockutil
brew install exiftool
brew install faad2
brew install md5sha1sum
brew install --with-qt5 mkvtoolnix
brew install openssl
brew install osxutils
brew install pstree
brew install ssh-copy-id
brew install watch
brew install webkit2png

# htop-osx requires root privileges to correctly display all running processes.
sudo chown root:wheel "$(brew --prefix)/bin/htop"
sudo chmod u+s "$(brew --prefix)/bin/htop"

# Install binary apps from homebrew.
for PACKAGE in $BIN_PACKAGES
do
   brew cask install "$PACKAGE"
done
brew cask install aerial
brew cask install android-file-transfer
brew cask install atom
brew cask install bitcoin-core
brew cask install chromium
brew cask install dropbox
brew cask install dupeguru
brew cask install flux
brew cask install ftdi-vcp-driver
brew cask install gitup
brew cask install google-drive
brew cask install google-play-music-desktop-player
brew cask install java
brew cask install kiwix
brew cask install libreoffice
brew cask install musicbrainz-picard
brew cask install music-manager
brew cask install openzfs
brew cask install rowanj-gitx
brew cask install spectacle
brew cask install steam
brew cask install torbrowser
brew cask install transmission
brew cask install tunnelblick
brew cask install virtualbox-extension-pack
brew cask install xbox360-controller-driver

# Install QuickLooks plugins
# Source: https://github.com/sindresorhus/quick-look-plugins
brew cask install epubquicklook
brew cask install qlcolorcode
brew cask install qlimagesize
brew cask install qlmarkdown
brew cask install qlstephen
brew cask install quicklook-json
brew cask install suspicious-package
qlmanage -r

# Install GNU `sed`, overwriting the built-in `sed`.
brew install gnu-sed --with-default-names

# Install more recent versions of some OS X tools.
brew install homebrew/dupes/grep
brew install homebrew/dupes/openssh

# Add extra filesystem support.
brew cask install osxfuse
brew install homebrew/fuse/ext2fuse
brew install homebrew/fuse/ext4fuse
brew install homebrew/fuse/ntfs-3g

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

# Install uBlock for Safari.
defaults read ~/Library/Safari/Extensions/extensions | grep --quiet "net.gorhill.uBlock"
if [[ $? -ne 0 ]]; then
    curl -o "$TMPDIR/ublock-safari.safariextz" -O https://cloud.delosent.com/ublock-safari-0.9.5.2.safariextz
    open "$TMPDIR/ublock-safari.safariextz"
fi

# Set chromium as the default browser.
brew install duti
duti -s org.chromium.Chromium http

# Install mpv.app so we can set it as default player
brew install mpv --with-bundle
brew linkapps mpv
duti -s io.mpv api
duti -s io.mpv mkv
duti -s io.mpv mp4

# Install Popcorn Time.
rm -rf ~/Applications/Popcorn-Time.app
wget -O - "https://get.popcorntime.sh/build/Popcorn-Time-0.3.9-Mac.tar.xz" | tar -xvJ --directory ~/Applications -f -

# Install and configure bitbar.
brew cask install bitbar
defaults write com.matryer.BitBar pluginsDirectory "~/.bitbar"
wget -O "${HOME}/.bitbar/btc.17m.sh" https://github.com/matryer/bitbar-plugins/raw/master/Bitcoin/bitfinex.com/bitfinex_btcusd.sh
wget -O "${HOME}/.bitbar/brew.1d.sh" https://github.com/matryer/bitbar-plugins/raw/master/Dev/Homebrew/brew-updates.1h.sh
wget -O "${HOME}/.bitbar/cask.1d.sh" https://github.com/matryer/bitbar-plugins/raw/master/Dev/Homebrew/homebrewcask.1d.sh
wget -O "${HOME}/.bitbar/netinfo.3m.sh" https://github.com/matryer/bitbar-plugins/raw/master/Network/netinfo.60s.sh
wget -O "${HOME}/.bitbar/disk.13m.sh" https://github.com/matryer/bitbar-plugins/raw/master/System/mdf.1m.sh
chmod +x ${HOME}/.bitbar/*.sh
open -a BitBar

# Clean things up.
brew linkapps
brew cleanup
brew prune
brew cask cleanup
