#!/usr/bin/env bash

# Install command line tools
xcode-select -p
if [[ $? -ne 0 ]]; then
    xcode-select --install
fi

# A full installation of Xcode.app is required to compile macvim.
# Installing just the Command Line Tools is not sufficient.
xcodebuild -version
if [[ $? -ne 0 ]]; then
    # TODO: find a way to install Xcode.app automatticaly
    # See: http://stackoverflow.com/a/18244349

    # Accept Xcode license
    sudo xcodebuild -license
fi

# Update all OSX packages
sudo softwareupdate -i -a

# Install Homebrew if not found
brew --version
if [[ $? -ne 0 ]]; then
    # Clean-up failed Homebrew install
    rm -rf "/usr/local/Cellar" "/usr/local/.git"
    # Install Homebrew
    ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"
fi
brew update
brew upgrade brew-cask
brew upgrade

# Include duplicates packages
brew tap homebrew/dupes

# Install Cask
brew tap caskroom/cask
brew install brew-cask

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
brew install colorsvn
brew install dockutil
brew install exiftool
brew install faad2
brew install hub
brew install md5sha1sum
brew install osxutils
brew install ssh-copy-id
brew install watch
brew install webkit2png

# Install Cassandra
brew install cassandra
pip install --upgrade cql

# htop-osx requires root privileges to correctly display all running processes.
sudo chown root:wheel "$(brew --prefix)/bin/htop"
sudo chmod u+s "$(brew --prefix)/bin/htop"

# Install binary apps
for PACKAGE in $BIN_PACKAGES
do
   brew cask install --force "$PACKAGE"
done
brew cask install --force bitcoin-core
brew cask install --force chromium
brew cask install --force dropbox
brew cask install --force flux
brew cask install --force gitx
brew cask install --force insync
brew cask install --force libreoffice
brew cask install --force sqlite-database-browser
brew cask install --force steam
brew cask install --force torbrowser
brew cask install --force tunnelblick

# Install QuickLooks plugins
# Source: https://github.com/sindresorhus/quick-look-plugins
brew cask install --force betterzipql
brew cask install --force cert-quicklook
brew cask install --force epubquicklook
brew cask install --force qlcolorcode
brew cask install --force qlmarkdown
brew cask install --force qlprettypatch
brew cask install --force qlstephen
brew cask install --force quicklook-csv
brew cask install --force quicklook-json
brew cask install --force suspicious-package
brew cask install --force webp-quicklook
qlmanage -r

# Add EXT support
brew cask install --force osxfuse
brew install ext2fuse
brew install ext4fuse

# Install vim
brew install lua --completion
brew install cscope
VIM_FLAGS="--with-python --with-lua --with-cscope --override-system-vim"
brew install macvim "$VIM_FLAGS"
# Always reinstall vim to fix Python links.
# See: https://github.com/yyuu/pyenv/issues/234
brew reinstall vim "$VIM_FLAGS"

# Remove previous install of refind bootloader first.
mkdir /Volumes/esp
sudo mount -t msdos /dev/disk0s1 /Volumes/esp
sudo rm -rf /Volumes/esp/EFI/refind
sudo rm -rf /Volumes/esp/EFI/BOOT
sudo diskutil umount /Volumes/esp
# Install custom bootloader.
curl -O http://softlayer-ams.dl.sourceforge.net/project/refind/0.8.7/refind-bin-0.8.7.zip
unzip ./refind-bin-0.8.7.zip
./refind-bin-0.8.7/install.sh --alldrivers
rm -rf ./refind-bin-0.8.7*
sudo diskutil umount /Volumes/esp
# Fix Yosemite boot. Source: http://www.rodsbooks.com/refind/yosemite.html
mkdir /Volumes/esp
sudo mount -t msdos /dev/disk0s1 /Volumes/esp
# Adjust personnal refind config
sudo sed -i "" -e "s/timeout 20/timeout 1/" /Volumes/esp/EFI/refind/refind.conf
sudo sed -i "" -e "s/#default_selection 1/default_selection linux/" /Volumes/esp/EFI/refind/refind.conf

# Install runsnakeerun
brew install wxmac
brew install wxpython
pip install --upgrade RunSnakeRun

# Install pgcli
brew install pgcli

# Clean things up
brew linkapps
brew cleanup
brew prune
brew cask cleanup
