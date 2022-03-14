#!/usr/bin/env zsh
set -Eeuxo pipefail


######### Pre-checks #########

# Detect platform.
if [ "$(uname -s)" != "Darwin" ]; then
    echo "These dotfiles only targets macOS."
    exit 1
fi

# Check current shell interpreter.
ps -p $$ | grep "zsh"
if [ $? != 0 ]; then
    echo "These dotfiles were tested with Zsh shell only."
    exit 1
fi

# Check if SIP is going to let us mess with some part of the system.
SIP_DISABLED=$(csrutil status | grep --quiet "enabled"; echo $?)
if [[ ${SIP_DISABLED} -ne 0 ]]; then
    echo "System Integrity Protection (SIP) is disabled."
else
    echo "System Integrity Protection (SIP) is enabled."
fi


######### Sudo keep-alive #########
# Source: https://gist.github.com/cowboy/3118588

# Ask for the administrator password upfront.
# Ignore the following error returns within GitHub actions workflows:
#   sudo: a terminal is required to read the password; either use the -S option to
#   read from standard input or configure an askpass helper
sudo --validate || true

# Update existing `sudo` time stamp until script has finished.
while true; do sleep 60; sudo --non-interactive true; kill -0 "$$" || exit; done 2> /dev/null &


######### Basic dependencies #########

# Command line tools provides a copy of git.
xcode-select --install || true


######### Symlink dotfiles in user's home #########

# Collect all entries within the "dotfiles" sub-folder, but the "Library".
DOT_FILES=$(command find dotfiles -depth 1 -not -name '\.DS_Store' -not -name 'Library')
# Collect all "Library subfolders" but "Application Support" folder.
DOT_FILES+="
$(command find dotfiles/Library -depth 1 -not -name '\.DS_Store' -not -name 'Application Support')"
# Collect all "Application Support" subfolders but "Code" folder.
DOT_FILES+="
$(command find 'dotfiles/Library/Application Support' -depth 1 -not -name '\.DS_Store' -not -name 'Code')"
# Manually add Code settings file.
DOT_FILES+="
dotfiles/Library/Application Support/Code/User/settings.json"

echo "Collected dotfiles:"
echo "${DOT_FILES}" | sort

for FILEPATH (${(f)DOT_FILES}); do
    DESTINATION="${PWD}/${FILEPATH}"
    LINK="${HOME}/${FILEPATH#*/}"
    CURRENT_LINK="$(readlink "${LINK}" || true)"
    if [[ "${CURRENT_LINK}" != "${DESTINATION}" ]]; then
        # Something (a link, a file, a directory...) already exists. Back it up.
        if [[ -e "${LINK}" ]]; then
            EXT=".dotfiles.bak"
            INC=0
            BACKUP="${LINK}${EXT}${INC}"
            while [ -f "${BACKUP}" ]; do
                ((INC++))
                BACKUP="${LINK}${EXT}${INC}"
            done
            echo "Backup: ${LINK} -> ${BACKUP}"
            mv "${LINK}" "${BACKUP}"
        fi
        # Force symbolic link (re-)creation. It either doesn't exist or point to the wrong place.
        echo "Create link: ${LINK} -> ${DESTINATION}"
        ln -sf "${DESTINATION}" "$(dirname "${LINK}")"
    fi
done


######### System upgrades #########

# Update all macOS packages.
sudo softwareupdate --install --all

# Some packages still needs Rosetta 2 on Apple Silicon.
# Skip installation on GitHub runners, which are Intel-based.
if (( ! ${+GITHUB_WORKFLOW} )); then
    sudo softwareupdate --install-rosetta --agree-to-license
fi


######### Brew install #########

# Check if homebrew is already installed. See: https://unhexium.net/zsh/how-to-check-variables-in-zsh/
# This also install xcode command line tools.
if (( ! ${+commands[brew]} )); then
    # Install Homebrew without prompting for user confirmation.
    # See: https://github.com/Homebrew/install/pull/139
    CI=true /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

# Activate brew analytics in GitHub actions, to prevent overzealous maintainers for
# removing perfectly working packages on the pretense nobody uses them.
if (( ! ${+GITHUB_WORKFLOW} )); then
    brew analytics on
else
    brew analytics off
fi

# Refresh our local copy of package index.
brew update

# Fetch latest packages.
brew upgrade

# Add services.
brew tap homebrew/services
brew tap gromgit/homebrew-fuse


######### Meta Package Manager #########

brew install python

# Expose Python 3 as default.
export PATH=$(brew --prefix python)/libexec/bin:$PATH

# Install mpm.
python -m pip install --upgrade pip
python -m pip install --upgrade meta-package-manager

# Refresh all package managers.
mpm --verbosity INFO sync

# Install all my packages but skip [mas] section (there is a circular
# dependency as mas needs to be install by brew first).
# XXX This edge-case should be taken care of upstream by mpm.
mpm --verbosity INFO --exclude mas restore ./packages.toml


######### Zsh #########

# Install zinit
sh -c "$(curl -fsSL https://git.io/zinit-install)"

# Fix "zsh compinit: insecure directories" error.
sudo chown -R $(whoami) /usr/local/share/zsh /usr/local/share/zsh/site-functions
chmod u+w /usr/local/share/zsh /usr/local/share/zsh/site-functions

# Generate pip and poetry completion.
python -m pip completion --zsh > ~/.zfunc/_pip
poetry completions zsh > ~/.zfunc/_poetry
_MPM_COMPLETE=zsh_source mpm > ~/.zfunc/_mpm

# Restart the shell.
exec zsh

# Force zinit self-upgrade.
zinit self-update
zinit delete --clean --yes
zinit update


######### Post-brew setup #########

# htop-osx requires root privileges to correctly display all running processes.
sudo chown root:wheel "$(brew --prefix)/bin/htop"
sudo chmod u+s "$(brew --prefix)/bin/htop"

# Activate and register MAC Address spoofing service if not already running.
if [[ ! -n $(sudo brew services info spoof-mac --json | jq '.[] | select(.name == "spoof-mac" and .loaded == true)') ]]; then
    sudo brew services restart spoof-mac
fi


######### Mac App Store packages #########

# Upgrade all desktop apps.
mpm --mas --verbosity INFO restore ./packages.toml

# Remove unused apps.
mas uninstall 682658836 || true  # GarageBand
mas uninstall 409201541 || true  # Pages

# Open apps so I'll not forget to login.
APP_NAMES="
1Password 7
adguard
Bitwarden
ProtonVPN
"
for APP_NAME (${(f)APP_NAMES})
do
    # Do not fail on missing app
    open -a "${APP_NAME}" || true
done

# Activate Safari extension.
# Source: https://github.com/kdeldycke/kevin-deldycke-blog/blob/main/content/posts/macos-commands.md
pluginkit -e use -i com.bitwarden.desktop.safari

# Fix "QL*.qlgenerator cannot be opened because the developer cannot be verified."
xattr -cr ~/Library/QuickLook/QLColorCode.qlgenerator
xattr -cr ~/Library/QuickLook/QLStephen.qlgenerator
# Clear plugin cache
qlmanage -r
qlmanage -r cache

# Configure xbar.
XBAR_PLUGINS_FOLDER="${HOME}/Library/Application Support/xbar/plugins"
mkdir -p "${XBAR_PLUGINS_FOLDER}"
wget -O "${XBAR_PLUGINS_FOLDER}/btc.17m.sh" https://raw.githubusercontent.com/matryer/xbar-plugins/main/Cryptocurrency/Bitcoin/bitstamp.net/last.10s.sh
sed -i "s/Bitstamp: /Ƀ/" "${XBAR_PLUGINS_FOLDER}/btc.17m.sh"
wget -O "${XBAR_PLUGINS_FOLDER}/brew-services.7m.rb" https://raw.githubusercontent.com/matryer/xbar-plugins/main/Dev/Homebrew/brew-services.10m.rb
chmod +x "${XBAR_PLUGINS_FOLDER}/"*.(sh|py|rb)
open -a xbar

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
https://protonmailrmez3lotccipshtkleegetolb73fuirgj7r4o4vfu7ozyd.onion,ProtonMail,ehmwyurmkort,eqeiuuEyivna
http://piratebayo3klnzokct3wt5yyxb2vpebbuyjl7m623iaxmqhsd52coid.onion,PirateBay,nnypemktnpya,dvzeeooowsgx
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

# Force installation of Firefox plugins.
wget https://addons.mozilla.org/firefox/downloads/latest/ublock-origin/addon-607454-latest.xpi -O "$TB_CONFIG_DIR/extensions/uBlock0@raymondhill.net.xpi"
wget https://addons.mozilla.org/firefox/downloads/latest/ether-metamask/addon-3885451-latest.xpi -O "$TB_CONFIG_DIR/extensions/webextension@metamask.io.xpi"

# Open IINA at least once in the background to let it register its Safari extension.
# Then close it after a while to not block script execution.
# This also pop-up a persistent, but non-blocking dialog:
# "XXX.app is an app downloaded from the Internet. Are you sure you want to open it?"
open --wait-apps -g -a "IINA" & sleep 20s; killall "IINA"

# Force Neovim plugin upgrades
nvim -c "try | call dein#update() | finally | qall! | endtry"


######### Cleanup #########

mpm --verbosity INFO cleanup
brew services cleanup


######### Configuration #########

export SIP_DISABLED
source ./macos-config.sh
unset SIP_DISABLED
