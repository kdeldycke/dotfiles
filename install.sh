#!/usr/bin/env zsh
set -Eeuxo pipefail

# Detect platform.
if [ "$(uname -s)" != "Darwin" ]; then
    echo "These dotfiles only targets macOS."
    exit 1
fi

# Check current shell interpreter.
ps -p $$ | grep "zsh"
if [ $? != 0 ]; then
    echo "These dotfiles were only tested with Zsh shell."
    exit 1
fi

# Ask for the administrator password upfront.
sudo -v

# TODO: install git here.

# Check if SIP is going to let us mess with some part of the system.
csrutil status | grep --quiet "disabled"
if [[ $? -ne 0 ]]; then
    echo "System Integrity Protection (SIP) is enabled."
else
    echo "System Integrity Protection (SIP) is disabled."
fi


######### Dotfiles install #########

# Search local dotfiles
DOT_FILES=$(command find ./dotfiles -maxdepth 1 -not -path './dotfiles' -not -name '\.DS_Store')
for FILEPATH (${(f)DOT_FILES}); do
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
sudo softwareupdate --install --all


######### Brew install #########

# Check if homebrew is already installed
# This also install xcode command line tools
if test ! "$(command -v brew)"
then
    # Install Homebrew without prompting for user confirmation.
    # See: https://github.com/Homebrew/install/pull/139
    CI=true /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install.sh)"
fi
brew analytics off
brew update
brew upgrade

# Add services
brew tap homebrew/services

# Load package lists to install.
source ./packages.sh

# Install brew packages.
for PACKAGE (${(f)BREW_PACKAGES}) brew install --formula "$PACKAGE"

# Install cask packages.
for PACKAGE (${(f)CASK_PACKAGES}) brew install --cask "$PACKAGE"

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
mas install 409183694
mas install 409203825

# Install 1Password.
mas install 1333542190
open -a "1Password 7"
# Activate Safari extension.
# Source: https://github.com/kdeldycke/kevin-deldycke-blog/blob/main/content/posts/macos-commands.md
pluginkit -e use -i com.agilebits.onepassword7.1PasswordSafariAppExtension

# WiFi Explorer Lite
mas install 1408727408

# Open apps so I'll not forget to login
open -a Dropbox
open -a adguard

# Spark - Email App by Readdle
mas install 1176895641

# Microsoft Remote Desktop
mas install 1295203466

# Install QuickLooks plugins
# Source: https://github.com/sindresorhus/quick-look-plugins
brew install --cask epubquicklook
brew install --cask qlcolorcode
brew install --cask qlimagesize
brew install --cask qlmarkdown
brew install --cask qlstephen
brew install --cask qlvideo
brew install --cask quicklook-json
brew install --cask suspicious-package
# Fix "QL*.qlgenerator cannot be opened because the developer cannot be verified."
xattr -cr ~/Library/QuickLook/QLColorCode.qlgenerator
xattr -cr ~/Library/QuickLook/QLMarkdown.qlgenerator
xattr -cr ~/Library/QuickLook/QLStephen.qlgenerator
# Clear plugin cache
qlmanage -r
qlmanage -r cache

# Install and configure Google Cloud Storage bucket mount point.
brew install gcsfuse
mkdir -p "${HOME}/gcs"
GOOGLE_APPLICATION_CREDENTIALS=~/.google-cloud-auth.json gcsfuse --implicit-dirs backup-imac-restic ./gcs
# Mount doesn't work as macOS doesn't let us register a new filesystem plugin.
# See: https://github.com/GoogleCloudPlatform/gcsfuse/issues/188
# sudo ln -s /usr/local/sbin/mount_gcsfuse /sbin/
# mount -t gcsfuse -o rw,user,keyfile="${HOME}/.google-cloud-auth.json" backup-imac-restic "${HOME}/gcs"


# Configure swiftbar.
defaults write com.ameba.SwiftBar PluginDirectory "~/.swiftbar"
defaults write com.ameba.SwiftBar SUHasLaunchedBefore 1
wget -O "${HOME}/.swiftbar/btc.17m.sh" https://github.com/matryer/bitbar-plugins/raw/master/Cryptocurrency/Bitcoin/bitstamp.net/last.10s.sh
sed -i "s/Bitstamp: /Ƀ/" "${HOME}/.swiftbar/btc.17m.sh"
wget -O "${HOME}/.swiftbar/brew-services.7m.rb" https://github.com/matryer/bitbar-plugins/raw/master/Dev/Homebrew/brew-services.10m.rb
chmod +x ${HOME}/.swiftbar/*.{sh,py,rb}
open -a SwiftBar

# Open Tor Browser at least once in the background to create a default profile.
# Then close it after a while to not block script execution.
open --wait-apps -g -a "Tor Browser" & sleep 20s; killall "firefox"
# Show TorBrowser bookmark toolbar.
TB_CONFIG_DIR=$(command find "${HOME}/Library/Application Support/TorBrowser-Data/Browser" -maxdepth 1 -iname "*.default")
tee -a "$TB_CONFIG_DIR/xulstore.json" <<-EOF
{"chrome://browser/content/browser.xhtml": {
    "PersonalToolbar": {"collapsed": "false"}
}}
EOF
# Set TorBrowser bookmarks in toolbar.
# Source: https://yro.slashdot.org/story/16/06/08/151245/kickasstorrents-enters-the-dark-web-adds-official-tor-address
BOOKMARKS="
https://protonirockerxow.onion,ProtonMail,ehmwyurmkort,eqeiuuEyivna
http://piratebayztemzmv.onion,PirateBay,nnypemktnpya,dvzeeooowsgx
"
TB_BOOKMARK_DB="$TB_CONFIG_DIR/places.sqlite"
# Remove all bookmarks from the toolbar.
sqlite3 -echo -header -column "$TB_BOOKMARK_DB" "DELETE FROM moz_bookmarks WHERE parent=(SELECT id FROM moz_bookmarks WHERE guid='toolbar_____'); SELECT * FROM moz_bookmarks;"
# Add bookmarks one by one.
for BM_INFO (${(f)BOOKMARKS})
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

# Open IINA at least once in the background to let it register its Safari extension.
# Then close it after a while to not block script execution.
# This also pop-up a persistent, but non-blocking dialog:
# "XXX.app is an app downloaded from the Internet. Are you sure you want to open it?"
open --wait-apps -g -a "IINA" & sleep 20s; killall "IINA"

# Clean things up.
brew cleanup
brew services cleanup

# Use latest pip.
python -m pip install --upgrade pip

# Install & upgrade all global python modules
for p (${(f)PYTHON_PACKAGES}) python -m pip install --upgrade "$p"

# Generate pip and poetry completion.
python -m pip completion --zsh > ~/.zfunc/_pip
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
