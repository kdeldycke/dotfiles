#TODO:
# install xcode
xcodebuild -license

# update all 

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
