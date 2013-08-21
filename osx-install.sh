# TODO: install xcode
# See: http://stackoverflow.com/a/18244349

# Accept Xcode license
xcodebuild -license

# TODO: install xcode's command line tools
# See: http://apple.stackexchange.com/a/98764

# TODO: update all OSX packages
# See: http://apple.stackexchange.com/questions/42353/can-mac-app-store-installs-upgrades-be-automated

# Install Homebrew
ruby -e "$(curl -fsSL https://raw.github.com/mxcl/homebrew/go)"
brew update
brew install git

# Install Python & co
brew install python
brew link --overwrite python
tee -a ~/.bash_profile <<-EOF
  export PATH="/usr/local/bin:\$PATH"
EOF
sudo pip install virtualenv

brew doctor
