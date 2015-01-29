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
brew upgrade

# Include duplicates packages
brew tap homebrew/dupes

# Install Cask
brew tap caskroom/cask
brew install brew-cask

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
   brew cask install "$PACKAGE"
done
brew cask install bitcoin-core
brew cask install chromium
brew cask install dropbox
brew cask install flux
brew cask install gitx
brew cask install insync
brew cask install libreoffice
brew cask install sqlite-database-browser
brew cask install steam
brew cask install torbrowser
brew cask install tunnelblick

# Install QuickLooks plugins
# Source: https://github.com/sindresorhus/quick-look-plugins
brew cask install betterzipql
brew cask install cert-quicklook
brew cask install epubquicklook
brew cask install qlcolorcode
brew cask install qlmarkdown
brew cask install qlprettypatch
brew cask install qlstephen
brew cask install quicklook-csv
brew cask install quicklook-json
brew cask install suspicious-package
brew cask install webp-quicklook
qlmanage -r

# Add EXT support
brew cask install osxfuse
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
curl -O http://softlayer-ams.dl.sourceforge.net/project/refind/0.8.3/refind-bin-0.8.3.zip
unzip ./refind-bin-0.8.3.zip
./refind-bin-0.8.3/install.sh --esp --alldrivers
rm -rf ./refind-bin-0.8.3*
sudo diskutil umount /Volumes/esp
# Fix Yosemite boot. Source: http://www.rodsbooks.com/refind/yosemite.html
mkdir /Volumes/esp
sudo mount -t msdos /dev/disk0s1 /Volumes/esp
sudo sed -i "" -e "s/#dont_scan_volumes \"Recovery HD\"/dont_scan_volumes/" /Volumes/esp/EFI/refind/refind.conf
# Adjust personnal refind config
sudo sed -i "" -e "s/timeout 20/timeout 1/" /Volumes/esp/EFI/refind/refind.conf
sudo sed -i "" -e "s/#default_selection 1/default_selection linux/" /Volumes/esp/EFI/refind/refind.conf
# Fix the 30-second delay before rEFInd appears when installed on ESP.
# Source: http://askubuntu.com/a/543121
sudo mv /Volumes/esp/EFI/refind/refind_x64.efi /Volumes/esp/EFI/refind/bootx64.efi
sudo mv /Volumes/esp/EFI/refind /Volumes/esp/EFI/BOOT

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
