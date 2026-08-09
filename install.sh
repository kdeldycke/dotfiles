#!/usr/bin/env zsh
set -Eeuxo pipefail


######### Stage selection #########

# The install procedure is decomposed into stages, each runnable on its own:
#   ./install.sh                    Full run: every stage, in the order below.
#   ./install.sh links              A single stage.
#   ./install.sh cleanup snapshot   Several stages, in the order given.
#   ./install.sh --list             Print available stage names.
STAGES=(links packages shell apps cleanup snapshot config)

if [[ "${1:-}" == "--list" ]]; then
    print -l "${STAGES[@]}"
    exit 0
fi

# Reject unknown stage names before any check or side effect below.
for stage ("$@"); do
    if (( ! ${STAGES[(Ie)${stage}]} )); then
        echo "Unknown stage: ${stage}. Available stages: ${STAGES[*]}" >&2
        exit 2
    fi
done

run_stages=("$@")
(( ${#run_stages} )) || run_stages=("${STAGES[@]}")


######### Pre-checks #########

# Detect platform.
if [ "$(uname -s)" != "Darwin" ]; then
    echo "These dotfiles only targets macOS."
    exit 1
fi

# Check current shell interpreter. A standalone pipeline + $? check would be
# aborted by set -e before reaching the test: keep the pipeline in the condition.
if ! ps -p $$ | grep --quiet "zsh"; then
    echo "These dotfiles were tested with Zsh shell only."
    exit 1
fi

# Check if SIP is going to let us mess with some part of the system.
if csrutil status 2>/dev/null | grep --quiet "enabled"; then
    SIP_DISABLED=0
    echo "System Integrity Protection (SIP) is enabled."
else
    SIP_DISABLED=1
    echo "System Integrity Protection (SIP) is disabled."
fi

# Use system, BSD find command. Shared by the links and apps stages.
FIND_CLI="/usr/bin/find"


######### Sudo keep-alive #########
# Source: https://gist.github.com/cowboy/3118588

# Ask for the administrator password upfront.
# Ignore the following error returns within GitHub actions workflows:
#   sudo: a terminal is required to read the password; either use the -S option to
#   read from standard input or configure an askpass helper
sudo --validate || true

# Update existing `sudo` time stamp until script has finished.
while true; do sleep 60; sudo --non-interactive true; kill -0 "$$" || exit; done 2> /dev/null &


######### Stage: links #########

# Symlink dotfiles in user's home.
stage_links() {
    # Collect all entries within the "dotfiles" sub-folder, but the "Library", ".config" and ".pi".
    DOT_FILES=$($FIND_CLI dotfiles -depth 1 -not -name '\.DS_Store' -not -name 'Library' -not -name '.config' -not -name '.pi')
    # Collect all ".config" content .
    DOT_FILES+="
$($FIND_CLI dotfiles/.config -depth 1 -not -name '\.DS_Store')"
    # Collect all "Library" subfolders but "Application Support" and "Preferences" folders.
    DOT_FILES+="
$($FIND_CLI dotfiles/Library -depth 1 -not -name '\.DS_Store' -not -name 'Application Support' -not -name 'Preferences')"
    # Collect all "Preferences" subfolders.
    DOT_FILES+="
$($FIND_CLI dotfiles/Library/Preferences -depth 1 -not -name '\.DS_Store')"
    # Collect all "Application Support" subfolders but "Code" folder.
    DOT_FILES+="
$($FIND_CLI 'dotfiles/Library/Application Support' -depth 1 -not -name '\.DS_Store' -not -name 'Code')"
    # Manually add Code and Pi settings files.
    DOT_FILES+="
dotfiles/Library/Application Support/Code/User/settings.json
dotfiles/.pi/agent/settings.json
dotfiles/.pi/agent/extensions"

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
                # -e, not -f: backed-up entries can be directories (~/.gnupg,
                # ~/.claude, ...). -f never matches a directory, so the counter
                # would stall and mv would drop the next backup inside the previous
                # one instead of beside it.
                while [ -e "${BACKUP}" ]; do
                    # += instead of ++: a post-increment from 0 evaluates to 0,
                    # whose non-zero exit status trips set -e.
                    (( INC += 1 ))
                    BACKUP="${LINK}${EXT}${INC}"
                done
                echo "Backup: ${LINK} -> ${BACKUP}"
                mv "${LINK}" "${BACKUP}"
            fi
            echo "Create link: ${LINK} -> ${DESTINATION}"
            # Create missing directory structure if missing.
            LINK_FOLDER="$(dirname "${LINK}")"
            mkdir -p "${LINK_FOLDER}"
            # Force symbolic link (re-)creation. It either doesn't exist or point to the wrong place.
            ln -sf "${DESTINATION}" "${LINK_FOLDER}"
        fi
    done
}


######### Stage: packages #########

# OS updates, Homebrew bootstrap and the full package restore via mpm.
stage_packages() {
    # Command line tools provides a copy of git.
    xcode-select --install || true

    # Install recommended macOS updates only: --all can also stage a
    # reboot-wanting OS upgrade in the middle of the bootstrap.
    #
    # Skipped on GitHub runners. The image is discarded at the end of the job,
    # so patching it buys nothing, and --recommended still pulls whole
    # multi-gigabyte point releases ("Downloading macOS Tahoe 26.6.1"): that
    # download was both the longest step of the run and, since softwareupdate
    # has no verbosity flag and prints one line per progress tick off a TTY,
    # the bulk of the log.
    if (( ! ${+GITHUB_WORKFLOW} )); then
        sudo softwareupdate --install --recommended
    fi

    # Check if homebrew is already installed. See: https://unhexium.net/zsh/how-to-check-variables-in-zsh/
    # This also install xcode command line tools.
    if (( ! ${+commands[brew]} )); then
        # Install Homebrew without prompting for user confirmation.
        NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
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

    # Add taps.
    brew tap smudge/smudge

    # Trust the specific third-party formulae I install from untrusted taps.
    brew trust --formula smudge/smudge/nightlight

    brew install "python@3.14"

    # Install mpm.
    brew install meta-package-manager

    # Refresh all package managers.
    mpm --verbosity INFO sync

    # Install all my packages but skip [mas] section (there is a circular
    # dependency as mas needs to be install by brew first).
    # XXX This edge-case should be taken care of upstream by mpm.
    mpm --verbosity INFO --no-mas restore ./packages.toml
}


######### Stage: shell #########

# Zsh plugins and completions.
stage_shell() {
    # Install zinit
    sh -c "$(curl -fsSL https://raw.githubusercontent.com/zdharma-continuum/zinit/HEAD/scripts/install.sh)"

    # Fix "zsh compinit: insecure directories" error.
    sudo chown -R $(whoami) "$(brew --prefix)/share/zsh" "$(brew --prefix)/share/zsh/site-functions"
    chmod u+w "$(brew --prefix)/share/zsh" "$(brew --prefix)/share/zsh/site-functions"

    # Generate pip and mpm completion. macOS ships no unversioned python binary.
    python3 -m pip completion --zsh > ~/.zfunc/_pip
    _MPM_COMPLETE=zsh_source mpm > ~/.zfunc/_mpm

    # Force zinit self-upgrade. Run in an interactive child shell, where .zshrc
    # defines the zinit function.
    zsh -ic "zinit self-update && zinit delete --clean --yes && zinit update"
}


######### Stage: apps #########

# Mac App Store packages and per-application setup.
stage_apps() {
    # htop-osx requires root privileges to correctly display all running processes.
    sudo chown root:wheel "$(brew --prefix)/bin/htop"
    sudo chmod u+s "$(brew --prefix)/bin/htop"

    # Upgrade all desktop apps. Skipped on GitHub runners: mas needs an Apple ID
    # interactively signed into the App Store app, which hosted runners don't
    # have, so every install hangs until mpm's per-package timeout and fails.
    if (( ! ${+GITHUB_WORKFLOW} )); then
        mpm --mas --verbosity INFO restore ./packages.toml
    fi

    # Remove unused apps.
    mas uninstall 682658836 || true  # GarageBand
    mas uninstall 409201541 || true  # Pages

    # Open apps so I'll not forget to login. Skipped on GitHub runners: there is
    # nobody there to log in, and an app that stops on a first-launch system
    # prompt (ProtonVPN asks to approve its VPN configuration) never finishes
    # launching, so `open -a` blocks until the job hits its timeout. The
    # trailing `|| true` only covers a missing app, not a hang.
    if (( ! ${+GITHUB_WORKFLOW} )); then
        APP_NAMES="
adguard
ProtonVPN
"
        for APP_NAME (${(f)APP_NAMES})
        do
            # Do not fail on missing app
            open -a "${APP_NAME}" || true
        done
    fi

    # Clear plugin cache
    qlmanage -r
    qlmanage -r cache

    # Configure SwiftBar.
    BAR_PLUGINS_FOLDER="${HOME}/Library/Application Support/SwiftBar/Plugins"
    mkdir -p "${BAR_PLUGINS_FOLDER}"
    ln -sf "$(mpm --bar-plugin-path)" "${BAR_PLUGINS_FOLDER}/meta_package_manager.7h.py"
    chmod +x "${BAR_PLUGINS_FOLDER}/"*.(sh|py|rb)
    # The rest of this stage seeds an app's profile by launching it, so it needs
    # a real login session and is skipped on GitHub runners. Without a session
    # the apps never come up and every step below takes the script down with it
    # under `set -e`: `killall` exits non-zero when its target never started,
    # and the `find` for the Tor profile exits non-zero when the directory that
    # launch was supposed to create is missing, which also leaves TB_CONFIG_DIR
    # empty and points the writes below at the filesystem root.
    if (( ! ${+GITHUB_WORKFLOW} )); then
        open -a SwiftBar

        # Open Tor Browser at least once in the background to create a default profile.
        # Then close it after a while to not block script execution.
        open --wait-apps -g -a "Tor Browser" & sleep 20s; killall "firefox"
        # Show TorBrowser bookmark toolbar.
        TB_CONFIG_DIR=$($FIND_CLI "${HOME}/Library/Application Support/TorBrowser-Data/Browser" -maxdepth 1 -iname "*.default")
        # Heredoc body and its EOF stay unindented: `<<-` strips leading tabs
        # only, so an indented terminator would never close the document.
        tee -a "$TB_CONFIG_DIR/xulstore.json" <<-EOF
{"chrome://browser/content/browser.xhtml": {
    "PersonalToolbar": {"collapsed": "false"}
}}
EOF
        # Set TorBrowser bookmarks in toolbar.
        # Source: https://yro.slashdot.org/story/16/06/08/151245/kickasstorrents-enters-the-dark-web-adds-official-tor-address
        # Entries stay unindented: leading blanks would end up in the values.
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
        # For privacy extensions, see: https://github.com/arkenfox/user.js/wiki/4.1-Extensions
        wget https://addons.mozilla.org/firefox/downloads/latest/ublock-origin/addon-607454-latest.xpi -O "$TB_CONFIG_DIR/extensions/uBlock0@raymondhill.net.xpi"

        # Open IINA at least once in the background to let it register its Safari extension.
        # Then close it after a while to not block script execution.
        # This also pop-up a persistent, but non-blocking dialog:
        # "XXX.app is an app downloaded from the Internet. Are you sure you want to open it?"
        open --wait-apps -g -a "IINA" & sleep 20s; killall "IINA"
    fi

    # Force Neovim plugin upgrades. vim.pack.update() opens a confirmation
    # buffer for review, so force=true is required to apply them unattended.
    nvim --headless -c "lua vim.pack.update(nil, { force = true })" -c "qall!"
}


######### Stage: cleanup #########

# Package caches, orphans, trash and DNS cache.
stage_cleanup() {
    mpm --verbosity INFO cleanup
    brew services cleanup

    # Empty the Trash on the startup disk and all mounted volumes.
    trash=(~/.Trash/*(N) /Volumes/*/.Trashes/*(N))
    (( ${#trash} )) && rm -rf "${trash[@]}" || true

    # Flush the DNS resolver cache.
    sudo dscacheutil -flushcache
    sudo killall -HUP mDNSResponder
}


######### Stage: snapshot #########

# Record the versions of currently installed packages into packages.toml.
stage_snapshot() {
    mpm --verbosity INFO snapshot --update-version ./packages.toml
}


######### Stage: config #########

# Apply the full macOS configuration. Warning: kills Terminal at the end.
stage_config() {
    export SIP_DISABLED
    source ./macos-config.sh
    unset SIP_DISABLED
}


######### Stage driver #########

for stage ("${run_stages[@]}"); do
    echo "=== Stage: ${stage} ==="
    "stage_${stage}"
done
