#!/usr/bin/env bash
source ./common.sh

function installcask() {
    brew cask install "${@}" 2> /dev/null
}

# TODO: install xcode
# See: http://stackoverflow.com/a/18244349

# Accept Xcode license
xcodebuild -license

# TODO: install xcode's command line tools
# See: http://apple.stackexchange.com/a/98764

# Update all OSX packages
sudo softwareupdate -i -a

# Install Homebrew
ruby -e "$(curl -fsSL https://raw.github.com/mxcl/homebrew/go)"
brew update
brew upgrade

# Install Cask
brew tap phinze/homebrew-cask
brew install brew-cask

# Install OSX system requirements
installcask x-quartz 

# Install common packages
brew install $SOURCE_PACKAGES

# htop-osx requires root privileges to correctly display all running processes.
sudo chown root:wheel /usr/local/bin/htop
sudo chmod u+s /usr/local/bin/htop

# Install OSX only packages
brew install findutils bash ack rename tree webkit2png bazaar osxutils htop-osx p7zip faad2 bash-completion md5sha1sum
brew tap homebrew/dupes
brew install homebrew/dupes/grep

# Install Python & co
brew install python
brew link --overwrite python
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

# Clean things up
brew doctor
brew cleanup
