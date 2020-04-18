#!/usr/bin/env zsh
set -x

# Detect platform.
if [ "$(uname -s)" != "Darwin" ]; then
    echo "These dotfiles only targets macOS."
    exit 1
fi
#echo $SHELL | grep 'zsh'
#if [[ $? -ne 0 ]]; then
#    echo "These dotfiles were only tested with Zsh shell."
#    exit 1
#fi

# Ask for the administrator password upfront.
sudo -v

# Keep-alive: update existing `sudo` time stamp until script has finished.
while true; do sudo -n true; sleep 60; kill -0 "$$" || exit; done 2>/dev/null &

# TODO: install git here.

# Check if SIP is going to let us mess with some part of the system.
csrutil status | grep --quiet "disabled"
if [[ $? -ne 0 ]]; then
    echo "System Integrity Protection (SIP) is enabled."
else
    echo "System Integrity Protection (SIP) is disabled."
fi


######### Dotfiles install #########

# Force initialization and update of local submodules.
git submodule update --recursive --remote

# Search local dotfiles
DOT_FILES=("${(@f)$(find ./dotfiles -maxdepth 1 -not -path './dotfiles' -not -name '\.DS_Store')}")
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


######### System upgrades #########

# Update all macOS packages.
sudo softwareupdate -i -a


######### Brew install #########

# Check if homebrew is already installed
# This also install xcode command line tools
if test ! "$(command -v brew)"
then
    # Install Homebrew without prompting for user confirmation.
    # See: https://github.com/Homebrew/install/pull/139
    CI=true ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"
fi
brew analytics off
brew update
brew upgrade

# Add Cask
brew tap caskroom/cask

# Add drivers.
brew tap caskroom/drivers

# Add services
brew tap homebrew/services

# Add fonts; these formulas needs SVN.
brew install subversion
brew tap homebrew/cask-fonts

# Install XQuartz beforehand to support Linux-based GUI Apps.
brew cask install xquartz

# Load package lists to install.
source ./packages.sh

# Install brew packages.
for PACKAGE in $BREW_PACKAGES
do
   brew install "$PACKAGE"
done

# Install cask packages.
for PACKAGE in $CASK_PACKAGES
do
   brew cask install "$PACKAGE"
done

# htop-osx requires root privileges to correctly display all running processes.
sudo chown root:wheel "$(brew --prefix)/bin/htop"
sudo chmod u+s "$(brew --prefix)/bin/htop"

# Activate auto MAC Address spoofing.
sudo brew services start spoof-mac


######### Mac App Store packages #########

# Install Mac App Store CLI and upgrade all apps.
brew install mas
mas upgrade

# Remove Pages and GarageBand.
sudo rm -rf /Applications/GarageBand.app
sudo rm -rf /Applications/Pages.app

# Install Numbers and Keynotes
mas lucky "Keynote"
mas lucky "Numbers"

# Install 1Password.
mas lucky "1Password 7"
open -a "1Password 7"
# Activate Safari extention.
# Source: https://github.com/kdeldycke/kevin-deldycke-blog/blob/master/content/posts/macos-commands.md
pluginkit -e use -i com.agilebits.onepassword7.1PasswordSafariAppExtension

# Open apps so I'll not forget to login
open -a Dropbox
open -a adguard

# Install Spark.
mas lucky "Spark - Email App by Readdle"

# Install QuickLooks plugins
# Source: https://github.com/sindresorhus/quick-look-plugins
brew cask install epubquicklook
brew cask install qlcolorcode
brew cask install qlimagesize
brew cask install qlmarkdown
brew cask install qlstephen
brew cask install qlvideo
brew cask install quicklook-json
brew cask install suspicious-package
qlmanage -r

# Install and configure Google Cloud Storage bucket mount point.
brew install gcsfuse
mkdir -p "${HOME}/gcs"
GOOGLE_APPLICATION_CREDENTIALS=~/.google-cloud-auth.json gcsfuse --implicit-dirs backup-imac-restic ./gcs
# Mount doesn't work as macOS doesn't let us register a new filesystem plugin.
# See: https://github.com/GoogleCloudPlatform/gcsfuse/issues/188
# sudo ln -s /usr/local/sbin/mount_gcsfuse /sbin/
# mount -t gcsfuse -o rw,user,keyfile="${HOME}/.google-cloud-auth.json" backup-imac-restic "${HOME}/gcs"

# Install Popcorn Time.
brew cask install https://raw.githubusercontent.com/popcorn-official/popcorn-desktop/development/casks/popcorn-time.rb

# Install and configure bitbar.
brew cask install bitbar
defaults write com.matryer.BitBar pluginsDirectory "~/.bitbar"
wget -O "${HOME}/.bitbar/btc.17m.sh" https://github.com/matryer/bitbar-plugins/raw/master/Cryptocurrency/Bitcoin/bitstamp.net/last.10s.sh
sed -i "s/Bitstamp: /Ƀ/" "${HOME}/.bitbar/btc.17m.sh"
wget -O "${HOME}/.bitbar/meta_package_manager.7h.py" https://github.com/kdeldycke/meta-package-manager/raw/develop/meta_package_manager/bitbar/meta_package_manager.7h.py
wget -O "${HOME}/.bitbar/brew-services.7m.rb" https://github.com/matryer/bitbar-plugins/raw/master/Dev/Homebrew/brew-services.10m.rb
chmod +x ${HOME}/.bitbar/*.{sh,py,rb}
open -a BitBar

# Open Tor Browser once to create a default profile.
open --wait-apps -a "Tor Browser"
# Show TorBrowser bookmark toolbar.
TB_CONFIG_DIR=$(find "${HOME}/Library/Application Support/TorBrowser-Data/Browser" -maxdepth 1 -iname "*.default")
sed -i "s/\"PersonalToolbar\":{\"collapsed\":\"true\"}/\"PersonalToolbar\":{\"collapsed\":\"false\"}/" "$TB_CONFIG_DIR/xulstore.json"
# Set TorBrowser bookmarks in toolbar.
# Source: https://yro.slashdot.org/story/16/06/08/151245/kickasstorrents-enters-the-dark-web-adds-official-tor-address
BOOKMARKS="
http://piratebayztemzmv.onion,PirateBay,nnypemktnpya,dvzeeooowsgx
"
TB_BOOKMARK_DB="$TB_CONFIG_DIR/places.sqlite"
# Remove all bookmarks from the toolbar.
sqlite3 -echo -header -column "$TB_BOOKMARK_DB" "DELETE FROM moz_bookmarks WHERE parent=(SELECT id FROM moz_bookmarks WHERE guid='toolbar_____'); SELECT * FROM moz_bookmarks;"
# Add bookmarks one by one.
for BM_INFO in $BOOKMARKS
do
    BM_URL=$(echo $BM_INFO | cut -d',' -f1)
    BM_TITLE=$(echo $BM_INFO | cut -d',' -f2)
    BM_GUID1=$(echo $BM_INFO | cut -d',' -f3)
    BM_GUID2=$(echo $BM_INFO | cut -d',' -f4)
    sqlite3 -echo -header -column "$TB_BOOKMARK_DB" "INSERT OR REPLACE INTO moz_places(url, hidden, guid, foreign_count) VALUES('$BM_URL', 0, '$BM_GUID1', 1); INSERT OR REPLACE INTO moz_bookmarks(type, fk, parent, title, guid) VALUES(1, (SELECT id FROM moz_places WHERE guid='$BM_GUID1'), (SELECT id FROM moz_bookmarks WHERE guid='toolbar_____'), '$BM_TITLE', '$BM_GUID2');"
done
sqlite3 -echo -header -column "$TB_BOOKMARK_DB" "SELECT * FROM moz_bookmarks; SELECT * FROM moz_places;"

# Force installation of uBlock origin
wget https://addons.mozilla.org/firefox/downloads/latest/ublock-origin/addon-607454-latest.xpi -O "$TB_CONFIG_DIR/extensions/uBlock0@raymondhill.net.xpi"

# Clean things up.
brew cleanup
brew services cleanup

# Use latest pip.
pip install --upgrade pip

# Fix brew/pip issue.
# Source: https://github.com/Homebrew/homebrew-core/issues/43866
# https://discourse.brew.sh/t/pip-install-upgrade-pip-breaks-pip-when-installed-with-homebrew/5338
ln -sf /usr/local/bin/pip $(brew --prefix python)/libexec/bin/pip

# Install & upgrade all global python modules
for p in $PYTHON_PACKAGES
do
    pip install --upgrade "$p"
done

# Generate pip and poetry completion.
pip completion --zsh > ~/.zfunc/_pip
poetry completions zsh > ~/.zfunc/_poetry
_MPM_COMPLETE=source_zsh mpm > ~/.zfunc/_mpm

# Force Neovim plugin upgrades
nvim -c "try | call dein#update() | finally | qall! | endtry"

# Install zinit
sh -c "$(curl -fsSL https://raw.githubusercontent.com/zdharma/zinit/master/doc/install.sh)"

# Fix "zsh compinit: insecure directories" error.
sudo chown -R $(whoami) /usr/local/share/zsh /usr/local/share/zsh/site-functions
chmod u+w /usr/local/share/zsh /usr/local/share/zsh/site-functions

# Force zinit self-upgrade.
zinit self-update
zinit update

# Configure everything.
source ./macos-config.sh
