#!/usr/bin/env bash

function installcask() {
    brew cask install "${@}" 2> /dev/null
}

# A full installation of Xcode.app is required to compile macvim.
# Installing just the Command Line Tools is not sufficient.
xcodebuild -version
if [[ $? -ne 0 ]]; then
    # TODO: find a way to install Xcode.app automatticaly
    # See: http://stackoverflow.com/a/18244349

    # Accept Xcode license
    sudo xcodebuild -license

    # Install Xcode's command line tools
    # Source: http://apple.stackexchange.com/a/98764
    curl -fsSL https://gist.github.com/trinitronx/6217746/raw/2c172e297fbafc3b8e0fcc6363df0b7b52e4ae6d/xcode-cli-tools.sh | sudo sh
fi

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
brew install python --with-brewed-openssl
brew link --overwrite python

# Install common packages
brew install $COMMON_PACKAGES

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
installcask dropbox
installcask steam
installcask f-lux
installcask gitx
installcask insync
installcask chromium
installcask libre-office
installcask tunnelblick
installcask prey

# Install vim
brew install lua --completion
brew install cscope
VIM_FLAGS="--with-python --with-lua --with-cscope --override-system-vim"
brew install macvim $VIM_FLAGS
brew install vim $VIM_FLAGS
# Patch the font defined by default for Terminale (Monaco, 11pt) for Vim's Airline plugin
# See: https://powerline.readthedocs.org/en/latest/fontpatching.html
brew install fontforge
mkdir ./powerline-fontconfig
curl -fsSL https://github.com/Lokaltog/powerline/tarball/develop | tar -xvz --strip-components 2 --include "*/font/*" --directory ./powerline-fontconfig -f -
fontforge -script ./powerline-fontconfig/fontpatcher.py /System/Library/Fonts/Monaco.dfont
sudo mv ./Monaco\ for\ Powerline.otf /System/Library/Fonts/
rm -rf ./powerline-fontconfig

# Clean things up
brew linkapps
brew doctor
brew cleanup
