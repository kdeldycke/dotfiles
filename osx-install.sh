#!/usr/bin/env bash
source ./common.sh

function installcask() {
    brew cask install "${@}" 2> /dev/null
}

# Install Xcode's command line tools
# Source: http://apple.stackexchange.com/a/98764
curl -fsSL https://gist.github.com/trinitronx/6217746/raw/2c172e297fbafc3b8e0fcc6363df0b7b52e4ae6d/xcode-cli-tools.sh | sudo sh

# Update all OSX packages
sudo softwareupdate -i -a

# Install Homebrew
ruby -e "$(curl -fsSL https://raw.github.com/mxcl/homebrew/go)"
brew update
brew upgrade

# Include duplicates packages
brew tap homebrew/dupes

# Install Cask
brew tap phinze/homebrew-cask
brew install brew-cask

# Install OSX system requirements
installcask x-quartz

# Install a brand new Python
brew install python
brew link --overwrite python

# Install common packages
brew install $SOURCE_PACKAGES

# Install OSX only packages
brew install findutils bash ack grep rename tree webkit2png bazaar osxutils htop-osx p7zip faad2 bash-completion md5sha1sum

# htop-osx requires root privileges to correctly display all running processes.
sudo chown root:wheel /usr/local/bin/htop
sudo chmod u+s /usr/local/bin/htop

# Install Python packages
sudo pip install --upgrade $PYTHON_PACKAGES

# Install binary apps
for PACKAGE in $BIN_PACKAGES
do
    installcask $PACKAGE
done
installcask f-lux
installcask gitx
installcask insync
installcask chromium
installcask iterm2
installcask libre-office
installcask tunnelblick
# TODO: install Prey when https://github.com/phinze/homebrew-cask/pull/953 and https://github.com/phinze/homebrew-cask/pull/954 are addressed.

# Install vim
brew install lua --completion
brew install cscope
VIM_FLAGS="--with-python --with-lua --with-cscope --override-system-vim"
brew install macvim $VIM_FLAGS
brew install vim $VIM_FLAGS
# TODO: detect currently used font in Terminal & patch it for Vim's Airline plugin
brew install fontforge
#wget https://raw.github.com/Lokaltog/powerline/develop/font/fontpatcher.py
# See: https://powerline.readthedocs.org/en/latest/fontpatching.html
#fontforge -script ./fontpatcher.py MyFontFile.ttf

brew linkapps

# Clean things up
brew doctor
brew cleanup
