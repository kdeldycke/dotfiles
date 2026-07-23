#!/usr/bin/env zsh
set -Eeuxo pipefail

###############################################################################
# Plist and preferences                                                       #
###############################################################################
# There is a couple of plist editing tools:
#
#  * defaults
#    Triggers update notification update to running process, but usage is
#    tedious.
#
#  * /usr/libexec/PlistBuddy
#    Great for big update, can create non-existing files.
#
#  * plutil
#    Can manipulate arrays and dictionaries with key paths.
#
# Sources:
#   * https://scriptingosx.com/2016/11/editing-property-lists/
#   * https://scriptingosx.com/2018/02/defaults-the-plist-killer/
#   * https://apps.tempel.org/PrefsEditor/index.php
#
# Some of these changes still require a logout/restart to take effect.

# Close any open System Settings panes, to prevent them from overriding
# settings we’re about to change
osascript -e 'tell application "System Settings" to quit'

# Extract hardware UUID to reconstruct host-dependent plists.
HOST_UUID=$(ioreg -d2 -c IOPlatformExpertDevice | awk -F\" '/IOPlatformUUID/{print $(NF-1)}')


###############################################################################
# Permissions and Access                                                      #
###############################################################################
# CLI to open the automation preference panel:
#   ❯ open "x-apple.systempreferences:com.apple.preference.security?Privacy_Automation"
#
# Raw list of permission names:
#   ❯ strings /System/Library/PrivateFrameworks/TCC.framework/Versions/Current/Resources/tccd | grep "^kTCCService[A-Z a-z]" | sort | uniq

# Ask for the administrator password upfront
sudo -v

# tccutil commands below only works if SIP is disabled.
if (( ${SIP_DISABLED:-0} )); then
    echo "System Integrity Protection (SIP) is disabled."

    # List existing entries for debug.
    sudo tccutil --list

    # Add Terminal as a developer tool. Any app referenced in the hidden Developer
    # Tools category will be able to bypass GateKeeper.
    # Source: an Apple Xcode engineer at:
    #   https://news.ycombinator.com/item?id=23278629
    #   https://news.ycombinator.com/item?id=23273867
    sudo spctl developer-mode enable-terminal
    sudo tccutil --service "kTCCServiceDeveloperTool" --insert "com.apple.Terminal"
    sudo tccutil --service "kTCCServiceDeveloperTool" --enable "com.apple.Terminal"

    # Since 10.15, BSD-userland processes now also deal with sandboxing, since the
    # BSD syscall ABI is now reimplemented in terms of macOS security capabilities.
    # Source: https://news.ycombinator.com/item?id=23274213
    #
    # Also, some plist preferences files are not readable either by the user or root
    # unless the Terminal.app gets Full Disk Access permission.
    #
    #   ❯ cat /Users/kde/Library/Preferences/com.apple.AddressBook.plist
    #   cat: /Users/kde/Library/Preferences/com.apple.AddressBook.plist: Operation not permitted
    #
    #   ❯ sudo cat /Users/kde/Library/Preferences/com.apple.AddressBook.plist
    #   Password:
    #   cat: /Users/kde/Library/Preferences/com.apple.AddressBook.plist: Operation not permitted

    # Grant Full Disk Access permission
    for app (
        "com.apple.Terminal"
        "/Applications/BlockBlock.app"
        "/Applications/KnockKnock.app"
    ); do
        sudo tccutil --service "kTCCServiceSystemPolicyAllFiles" --insert "${app}"
        sudo tccutil --service "kTCCServiceSystemPolicyAllFiles" --enable "${app}"
    done

    # Grant Accessibility permission
    for app (
        "/Applications/Amethyst.app"
        "/Library/Application Support/Logitech.localized/Logitech Options.localized/Logi Options Daemon.app"
        "/Applications/Logi Options.app"
        "/Applications/MonitorControl.app"
    ); do
        sudo tccutil --insert "${app}"
        sudo tccutil --enable "${app}"
    done

fi


###############################################################################
# General UI/UX                                                               #
###############################################################################

# Transform '  |   "model" = <"MacBookAir8,1">' to 'MBA'
COMPUTER_MODEL_SHORTHAND=$(ioreg -c IOPlatformExpertDevice -d 2 -r | grep '"model" =' | python -c "print(''.join([c for c in input() if c.isupper()]))")
COMPUTER_NAME="$(whoami)-${COMPUTER_MODEL_SHORTHAND}"
# Set computer name (as done via System Settings → General → About)
sudo scutil --set ComputerName "${COMPUTER_NAME}"
sudo scutil --set HostName "${COMPUTER_NAME}"
sudo scutil --set LocalHostName "${COMPUTER_NAME}"
sudo defaults write /Library/Preferences/SystemConfiguration/com.apple.smb.server NetBIOSName -string "${COMPUTER_NAME}"

# Remove default content
sudo rm -rf "${HOME}/Public/Drop Box"
rm -rf "${HOME}/Public/.com.apple.timemachine.supported"
rm -f "${HOME}/Desktop/SamsungPortableSSD.app"

# Disable the sound effects on boot
sudo nvram SystemAudioVolume=" "

# Enable ctrl+option+cmd to drag windows.
defaults write com.apple.universalaccess NSWindowShouldDragOnGesture -string "YES"

# Enable auto dark mode
defaults write NSGlobalDomain AppleInterfaceStyle -string "Dark"
defaults write NSGlobalDomain AppleInterfaceStyleSwitchesAutomatically -bool true

# Set highlight color to green
#defaults write NSGlobalDomain AppleHighlightColor -string "0.764700 0.976500 0.568600"

# Enable graphite appearance.
#defaults write NSGlobalDomain AppleAquaColorVariant -int 6

# Set sidebar icon size to medium
defaults write NSGlobalDomain NSTableViewDefaultSizeMode -int 2

# Always show scrollbars
defaults write NSGlobalDomain AppleShowScrollBars -string "Always"
# Possible values: `WhenScrolling`, `Automatic` and `Always`

# Disable the over-the-top focus ring animation
defaults write NSGlobalDomain NSUseAnimatedFocusRing -bool false

# Adjust toolbar title rollover delay
defaults write NSGlobalDomain NSToolbarTitleViewRolloverDelay -float 0

# Disable smooth scrolling
# (Uncomment if you’re on an older Mac that messes up the animation)
#defaults write NSGlobalDomain NSScrollAnimationEnabled -bool false

# Increase window resize speed for Cocoa applications
defaults write NSGlobalDomain NSWindowResizeTime -float 0.001

# Ask to keep changes when closing documents
defaults write NSGlobalDomain NSCloseAlwaysConfirmsChanges -bool true

# Don't keep recent items for Documents, Apps and Servers.
osascript << EOF
  tell application "System Events"
    tell appearance preferences
      set recent documents limit to 5
      set recent applications limit to 5
      set recent servers limit to 5
    end tell
  end tell
EOF

# Expand save panel by default
defaults write NSGlobalDomain NSNavPanelExpandedStateForSaveMode -bool true
defaults write NSGlobalDomain NSNavPanelExpandedStateForSaveMode2 -bool true

# Expand print panel by default
defaults write NSGlobalDomain PMPrintingExpandedStateForPrint -bool true
defaults write NSGlobalDomain PMPrintingExpandedStateForPrint2 -bool true

# Automatically quit printer app once the print jobs complete
defaults write com.apple.print.PrintingPrefs "Quit When Finished" -bool true

# Disable the “Are you sure you want to open this application?” dialog
defaults write com.apple.LaunchServices LSQuarantine -bool false

# Remove duplicates in the “Open With” menu (also see `lscleanup` alias)
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -kill -r -domain local -domain system -domain user

# Display ASCII control characters using caret notation in standard text views
# Try e.g. `cd /tmp; unidecode "\x{0000}" > cc.txt; open -e cc.txt`
defaults write NSGlobalDomain NSTextShowsControlCharacters -bool true

# Keep all windows open from previous session.
defaults write com.apple.systempreferences NSQuitAlwaysKeepsWindows -bool true

# Disable automatic termination of inactive apps
defaults write NSGlobalDomain NSDisableAutomaticTermination -bool true

# Disable the crash reporter
defaults write com.apple.CrashReporter DialogType -string "none"

# Set Help Viewer windows to non-floating mode
defaults write com.apple.helpviewer DevMode -bool true

# Reveal IP address, hostname, OS version, etc. when clicking the clock
# in the login window
sudo defaults write /Library/Preferences/com.apple.loginwindow AdminHostInfo -string "HostName"

# Disable automatic capitalization as it’s annoying when typing code
defaults write NSGlobalDomain NSAutomaticCapitalizationEnabled -bool false

# Disable smart dashes as they’re annoying when typing code
defaults write NSGlobalDomain NSAutomaticDashSubstitutionEnabled -bool false

# Disable automatic period substitution as it’s annoying when typing code
defaults write NSGlobalDomain NSAutomaticPeriodSubstitutionEnabled -bool false

# Disable smart quotes as they’re annoying when typing code
defaults write NSGlobalDomain NSAutomaticQuoteSubstitutionEnabled -bool false

# Disable auto-correct
defaults write NSGlobalDomain NSAutomaticSpellingCorrectionEnabled -bool false

# Set a custom wallpaper image. `DefaultDesktop.jpg` is already a symlink, and
# all wallpapers are in `/Library/Desktop Pictures/`. The default is `Wave.jpg`.
#rm -rf "${HOME}/Library/Application Support/Dock/desktoppicture.db"
#sudo rm -rf /System/Library/CoreServices/DefaultDesktop.jpg
#sudo ln -s /path/to/your/image /System/Library/CoreServices/DefaultDesktop.jpg

# Play user interface sound effects
defaults write -globalDomain "com.apple.sound.uiaudio.enabled" -int 0

# Play feedback when volume is changed
defaults write -globalDomain "com.apple.sound.beep.feedback" -int 0


##############################################################################
# Menubar                                                                    #
##############################################################################

# Disable transparency in the menu bar and elsewhere on Yosemite
#defaults write com.apple.universalaccess reduceTransparency -bool true

# Enable input menu in menu bar.
defaults write com.apple.TextInputMenu visible -bool true
defaults write com.apple.TextInputMenuAgent "NSStatusItem Visible Item-0" -bool true

# Menu bar: hide the User and Battery icons
defaults -currentHost write dontAutoLoad -array \
        "/System/Library/CoreServices/Menu Extras/User.menu"
defaults write com.apple.systemuiserver menuExtras -array \
        "/System/Library/CoreServices/Menu Extras/TimeMachine.menu" \
        "/System/Library/CoreServices/Menu Extras/AirPort.menu" \
        "/System/Library/CoreServices/Menu Extras/Bluetooth.menu" \
        "/System/Library/CoreServices/Menu Extras/TextInput.menu" \
        "/System/Library/CoreServices/Menu Extras/Volume.menu" \
        "/System/Library/CoreServices/Menu Extras/Clock.menu"

# Autohide dock and menubar.
#defaults write NSGlobalDomain _HIHideMenuBar -bool true


##############################################################################
# Security                                                                   #
##############################################################################
# Also see: https://github.com/drduh/macOS-Security-and-Privacy-Guide

# The application firewall configuration moved out of
# /Library/Preferences/com.apple.alf in macOS 15: defaults writes there are
# silently ignored. socketfilterfw is the supported CLI. Firewall events now
# land in the unified log, and the old logging toggle is gone.
# Enable firewall (mSCP: system_settings_firewall_enable).
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setglobalstate on

# Enable stealth mode (mSCP: system_settings_firewall_stealth_mode_enable).
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setstealthmode on

# Do not automatically allow built-in and downloaded signed software to
# receive incoming connections.
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setallowsigned off
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setallowsignedapp off

# Apply configuration on all network interfaces.
#   $ networksetup -listallnetworkservices
#   An asterisk (*) denotes that a network service is disabled.
#   Thunderbolt Ethernet Slot 1, Port 1
#   *Thunderbolt Ethernet Slot 1, Port 2
#   Wi-Fi
#   iPhone USB
#   Bluetooth PAN
#   Thunderbolt Bridge
net_interfaces=$(networksetup -listallnetworkservices | awk '{gsub(/^*/,""); if(NR>1)print}')
for net_service (${(f)net_interfaces}); do
    # Use Cloudflare's fast and privacy friendly DNS.
    networksetup -setdnsservers "${net_service}" 1.1.1.1 1.0.0.1 2606:4700:4700::1111 2606:4700:4700::1001
    # Clear out all search domains.
    networksetup -setsearchdomains "${net_service}" "Empty"
    # Setup 10G NIC.
    if [ "${net_service}" = "Thunderbolt Ethernet Slot 1, Port 2" ]; then
        networksetup -setMTU "${net_service}" 9000
    fi
done

# Disable wifi captive portal
sudo defaults write /Library/Preferences/SystemConfiguration/com.apple.captive.control Active -bool false

# Disable remote apple events (mSCP: system_settings_rae_disable).
sudo systemsetup -setremoteappleevents off
sudo launchctl disable system/com.apple.AEServer

# Disable remote login (SSH) and pin the service off across upgrades
# (mSCP: system_settings_ssh_disable). systemsetup requires Full Disk Access
# on the parent process, and -f skips the confirmation prompt.
sudo systemsetup -f -setremotelogin off
sudo launchctl disable system/com.openssh.sshd

# Explicitly disable the remaining sharing services. Most are already off by
# default, but pinning them keeps a known-good state across macOS upgrades.
# Screen sharing (CIS 2.4.3)
sudo launchctl disable system/com.apple.screensharing
# Remote management / Apple Remote Desktop (CIS 2.4.9)
sudo /System/Library/CoreServices/RemoteManagement/ARDAgent.app/Contents/Resources/kickstart -deactivate -stop
# File sharing over SMB (CIS 2.4.8)
sudo launchctl disable system/com.apple.smbd
# Printer sharing (CIS 2.4.4)
sudo cupsctl --no-share-printers
# DVD or CD sharing (CIS 2.4.6)
sudo launchctl disable system/com.apple.ODSAgent
# NFS server (CIS 4.5)
sudo launchctl disable system/com.apple.nfsd
# Apache HTTP server (CIS 4.4)
sudo launchctl disable system/org.apache.httpd

# Disable Internet Sharing. Off by default, this pins it; only a
# configuration profile can prevent re-enablement
# (mSCP: system_settings_internet_sharing_disable).
sudo defaults write /Library/Preferences/SystemConfiguration/com.apple.nat NAT -dict Enabled -int 0

# Disable Bluetooth sharing (mSCP: system_settings_bluetooth_sharing_disable).
defaults -currentHost write com.apple.Bluetooth PrefKeyServicesEnabled -bool false

# Disable AirPlay receiver. Apple fixed the misspelled key at some point and
# both spellings coexist, so pin the two
# (mSCP: system_settings_airplay_receiver_disable).
defaults -currentHost write com.apple.controlcenter AirplayReceiverEnabled -bool false
defaults -currentHost write com.apple.controlcenter AirplayReceiverEnabled -bool false

# Disable SMB guest access (mSCP: system_settings_guest_access_smb_disable).
sudo sysadminctl -smbGuestAccess off

# Disable the root account by pointing its shell at /usr/bin/false (CIS 5.6).
sudo dscl . -create /Users/root UserShell /usr/bin/false

# Disable Power Nap, so the machine stays asleep instead of waking to sync
# mail and updates (CIS 2.9).
sudo pmset -a powernap 0

# Disable wake-on modem
# XXX setwakeonmodem returns "Wake On Modem: Not supported on this machine." for now.
#sudo systemsetup -setwakeonmodem off
sudo pmset -a ring 0

# Disable wake-on LAN
sudo systemsetup -setwakeonnetworkaccess off
sudo pmset -a womp 0

# Display login window as name and password
sudo defaults write /Library/Preferences/com.apple.loginwindow SHOWFULLNAME -bool true

# Do not show password hints
sudo defaults write /Library/Preferences/com.apple.loginwindow RetriesUntilHint -int 0

# Remove password hints already stored on user records
# (mSCP: os_password_hint_remove).
for u ($(dscl . -list /Users UniqueID | awk '$2 > 500 {print $1}')); do
    sudo dscl . -delete "/Users/${u}" hint &> /dev/null || true
done

# Disable guest account login
sudo defaults write /Library/Preferences/com.apple.loginwindow GuestEnabled -bool false

# Remove the Guest home folder (mSCP: os_guest_folder_removed).
sudo rm -rf /Users/Guest

# Disable automatic login
sudo defaults delete /Library/Preferences/com.apple.loginwindow autoLoginUser || true

# Unlocking a locked session requires the password of the signed-in user,
# not that of any admin (mSCP: os_unlock_active_user_session_disable). The
# Platform SSO variant of the rule does not apply to a personal machine.
sudo security -q authorizationdb write system.login.screensaver "authenticate-session-owner"

# Require an administrator password for the system-wide preference panes,
# and do not share their unlocked state between panes
# (mSCP: system_settings_system_wide_preferences_configure).
for section (
    system.preferences
    system.preferences.energysaver
    system.preferences.network
    system.preferences.printing
    system.preferences.sharing
    system.preferences.softwareupdate
    system.preferences.startupdisk
    system.preferences.timemachine
); do
    authdb_plist="/tmp/${section}.plist"
    sudo security -q authorizationdb read "${section}" > "${authdb_plist}"
    for key_type_value (
        "class string user"
        "shared bool false"
        "authenticate-user bool true"
        "session-owner bool false"
        "group string admin"
    ); do
        parts=(${=key_type_value})
        /usr/libexec/PlistBuddy -c "Set :${parts[1]} ${parts[3]}" "${authdb_plist}" 2> /dev/null \
            || /usr/libexec/PlistBuddy -c "Add :${parts[1]} ${parts[2]} ${parts[3]}" "${authdb_plist}"
    done
    sudo security -q authorizationdb write "${section}" < "${authdb_plist}"
    rm -f "${authdb_plist}"
done

# A lost machine might be lucky and stumble upon a Good Samaritan.
sudo defaults write /Library/Preferences/com.apple.loginwindow LoginwindowText \
    "Found this computer? Please contact me at lost@deldycke.net"

# Automatically lock the login keychain for inactivity after 6 hours.
security set-keychain-settings -t 21600 -l "${HOME}/Library/Keychains/login.keychain"

# Destroy FileVault key when going into standby mode, forcing a re-auth.
# Source: https://web.archive.org/web/20160114141929/https://training.apple.com/pdf/WP_FileVault2.pdf
sudo pmset destroyfvkeyonstandby 1

# Add sudo 2FA based on Touch ID. Source: https://twitter.com/cabel/status/931292107372838912
# sudo tee -a "/etc/pam.d/sudo" <<-EOF
# auth       sufficient     pam_tid.so
# EOF

# Enable FileVault (if not already enabled)
# This requires a user password, and outputs a recovery key that should be
# copied to a secure location
if [[ $(sudo fdesetup status | head -1) == "FileVault is Off." ]]; then
  sudo fdesetup enable -user $(whoami)
fi

# Disable automatic login when FileVault is enabled
#sudo defaults write /Library/Preferences/com.apple.loginwindow DisableFDEAutoLogin -bool true

# Disable Bonjour multicast advertisements (mSCP: os_bonjour_disable)
sudo defaults write /Library/Preferences/com.apple.mDNSResponder.plist NoMulticastAdvertisements -bool true

# Show location icon in menu bar when System Services request your location.
sudo defaults write /Library/Preferences/com.apple.locationmenu.plist ShowSystemServices -bool true

# Install certs
wget -O "${HOME}/NextDNS.cer" https://nextdns.io/ca
sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain "${HOME}/NextDNS.cer"
rm -rfv "${HOME}/NextDNS.cer"

# Secure home folders from other local users, non-recursively as mSCP does
# (mSCP: os_home_folders_secure).
for home_dir (/Users/*(N/)); do
    [[ "${home_dir:t}" == "Shared" ]] && continue
    sudo chmod og-rwx "${home_dir}"
done

# Strip world-write from system support folders and system-wide apps
# (mSCP: os_world_writable_system_folder_configure /
# os_system_wide_applications_configure).
sudo command find /System/Volumes/Data/System -type d -perm -2 ! -path '*downloadDir*' ! -path '*locks*' -exec chmod o-w '{}' + 2> /dev/null || true
sudo command find /Applications -iname '*.app' -type d -perm -2 -exec chmod -R o-w '{}' + 2> /dev/null || true

# Keep system.log for 90 days. The application firewall now logs to the
# unified log: there is no appfirewall.log rotation to configure anymore.
sudo perl -p -i -e 's/rotate=seq compress file_max=5M all_max=50M/rotate=utc compress file_max=5M ttl=90/g' "/etc/asl.conf"

# Log authentication events for 90 days.
sudo perl -p -i -e 's/rotate=seq file_max=5M all_max=20M/rotate=utc file_max=5M ttl=90/g' "/etc/asl/com.apple.authd"

# Log installation events for a year (mSCP: os_install_log_retention_configure).
# The old format=bsd anchor is gone from the macOS 26 config, so replace the
# whole install.log line, mSCP-style, which also drops the all_max cap. Pin
# the BSD sed: Homebrew's GNU sed shadows it in PATH and parses -i differently.
sudo /usr/bin/sed -i '' "s/\* file \/var\/log\/install.log.*/\* file \/var\/log\/install.log format='\$\(\(Time\)\(JZ\)\) \$Host \$\(Sender\)\[\$\(PID\\)\]: \$Message' rotate=utc compress file_max=50M size_only ttl=365/g" /etc/asl/com.apple.install

# auditd is deprecated by Apple and ships disabled since macOS 14, without
# even a stub config: seed /etc/security/audit_control from the example and
# turn the service back on (mSCP: audit_auditd_enabled).
if [[ ! -e /etc/security/audit_control && -e /etc/security/audit_control.example ]]; then
    sudo cp /etc/security/audit_control.example /etc/security/audit_control
fi
# Audit authentication, administrative, file deletion and permission change
# events on top of the login/logout defaults (mSCP: audit_flags_*).
sudo perl -p -i -e 's|^flags:.*|flags:lo,aa,ad,fd,fm,-all,^-fa,^-fc,^-cl|' /etc/security/audit_control
# Rotate audit trails at 10M and keep 30 days of them
# (mSCP: audit_retention_configure).
sudo perl -p -i -e 's|^filesz:.*|filesz:10M|' /etc/security/audit_control
sudo perl -p -i -e 's|^expire-after:.*|expire-after:30d|' /etc/security/audit_control
sudo launchctl enable system/com.apple.auditd
sudo launchctl bootstrap system /System/Library/LaunchDaemons/com.apple.auditd.plist || true
sudo audit -i || true
# Tighten audit config and trail ownership, modes and ACLs
# (mSCP: audit_control_* / audit_files_* / audit_folder*_configure /
# audit_acls_*).
sudo chown root:wheel /etc/security/audit_control
sudo chmod 440 /etc/security/audit_control
sudo chmod -N /etc/security/audit_control
if [[ -d /var/audit ]]; then
    sudo chown root:wheel /var/audit
    sudo chmod 700 /var/audit
    sudo zsh -c 'chmod -RN /var/audit && chown root:wheel /var/audit/* && chmod 440 /var/audit/*' 2> /dev/null || true
fi

# Cap sudo credential caching at 5 minutes (the macOS default, pinned: CIS
# prefers 0 but that would prompt on every sudo line of this very script),
# keep per-tty timestamps and log allowed commands
# (mSCP: os_sudo_timeout_configure / os_sudoers_timestamp_type_configure /
# os_sudo_log_enforce).
sudo command find /etc/sudoers* -type f -exec /usr/bin/sed -i '' '/timestamp_timeout/d; /timestamp_type/d; /!tty_tickets/d; /!log_allowed/d' '{}' \;
sudo tee /etc/sudoers.d/mscp.tmp > /dev/null <<EOF
Defaults timestamp_timeout=5
Defaults log_allowed
EOF
sudo chmod 440 /etc/sudoers.d/mscp.tmp
# Validate before install: a broken sudoers.d file locks sudo out. The .tmp
# name is skipped by sudo (names with a dot are ignored) until the rename.
sudo visudo -c -f /etc/sudoers.d/mscp.tmp
sudo mv /etc/sudoers.d/mscp.tmp /etc/sudoers.d/mscp

# Activates Touch ID for sudo and make it persistent.
# See: https://sixcolors.com/post/2023/08/in-macos-sonoma-touch-id-for-sudo-can-survive-updates/
sudo cp /etc/pam.d/sudo_local.template /etc/pam.d/sudo_local
sudo sed -i "s/#auth/auth/" /etc/pam.d/sudo_local


###############################################################################
# Privacy: telemetry and data sharing                                         #
###############################################################################

# Do not auto-submit diagnostics and usage data to Apple, nor share crash
# data with app developers. This is the plist behind System Settings →
# Privacy & Security → Analytics & Improvements
# (mSCP: system_settings_diagnostics_reports_disable).
sudo defaults write "/Library/Application Support/CrashReporter/DiagnosticMessagesHistory.plist" AutoSubmit -bool false
sudo defaults write "/Library/Application Support/CrashReporter/DiagnosticMessagesHistory.plist" ThirdPartyDataSubmit -bool false

# Opt out of sharing Siri and dictation recordings with Apple, and of search
# queries data sharing (mSCP: system_settings_improve_siri_dictation_disable
# / system_settings_improve_search_disable).
defaults write com.apple.assistant.support 'Siri Data Sharing Opt-In Status' -int 2
defaults write com.apple.assistant.support 'Search Queries Data Sharing Status' -int 2

# Do not donate audio recordings to improve accessibility voice features
# (mSCP: system_settings_improve_assistive_voice_disable).
defaults write com.apple.Accessibility AXSAudioDonationSiriImprovementEnabled -bool false

# Disable Siri. Only the allowAssistant configuration profile key can
# prevent re-enablement (mSCP: system_settings_siri_disable).
defaults write com.apple.assistant.support 'Assistant Enabled' -bool false

# Opt out of Apple personalized advertising
# (mSCP: system_settings_personalized_advertising_disable).
defaults write com.apple.AdLib allowApplePersonalizedAdvertising -bool false


###############################################################################
# Privacy: metadata cache cleanup                                             #
###############################################################################
# Wipe the local caches macOS keeps about what I type, preview and download.
# Adapted from the drduh guide and alichtman/stronghold, made idempotent and
# safe under `set -e`. Caches only: nothing is frozen, so macOS stays free to
# rebuild them as normal.

# Clear the keyboard / spelling / suggestion language models. macOS will
# repopulate them from future typing.
for dir (
    "${HOME}/Library/LanguageModeling"
    "${HOME}/Library/Spelling"
    "${HOME}/Library/Suggestions"
); do
    [[ -d "${dir}" ]] || continue
    sudo find "${dir}" -mindepth 1 -delete || true
done

# Flush the QuickLook thumbnail cache, which retains previews (and their
# metadata) of files even from removed or encrypted volumes.
qlmanage -r cache &> /dev/null || true
ql_dir="${HOME}/Library/Application Support/Quick Look"
[[ -d "${ql_dir}" ]] && sudo find "${ql_dir}" -mindepth 1 -delete || true

# Clear Siri's local analytics database.
rm -fv "${HOME}/Library/Assistant/SiriAnalytics.db" || true

# Wipe the LaunchServices quarantine log (per-download source URLs and
# timestamps). LaunchServices repopulates it on the next download.
quarantine_db="${HOME}/Library/Preferences/com.apple.LaunchServices.QuarantineEventsV2"
[[ -f "${quarantine_db}" ]] && : > "${quarantine_db}" || true


###############################################################################
# Trackpad, mouse, keyboard, Bluetooth accessories and input                  #
###############################################################################

# Set mouse and scrolling speed.
defaults write NSGlobalDomain com.apple.mouse.scaling -int 3
defaults write NSGlobalDomain com.apple.trackpad.scaling -int 3
defaults write NSGlobalDomain com.apple.scrollwheel.scaling -float 0.6875

# Trackpad: enable tap to click for this user and for the login screen
defaults write com.apple.driver.AppleBluetoothMultitouch.trackpad Clicking -bool true
defaults write com.apple.AppleMultitouchTrackpad Clicking -bool true
defaults -currentHost write NSGlobalDomain com.apple.mouse.tapBehavior -int 1
defaults write NSGlobalDomain com.apple.mouse.tapBehavior -int 1

# Trackpad: right-click by tapping with two fingers
defaults write com.apple.driver.AppleBluetoothMultitouch.trackpad TrackpadCornerSecondaryClick -int 2
defaults write com.apple.driver.AppleBluetoothMultitouch.trackpad TrackpadRightClick -bool true
defaults -currentHost write NSGlobalDomain com.apple.trackpad.trackpadCornerClickBehavior -int 1
defaults -currentHost write NSGlobalDomain com.apple.trackpad.enableSecondaryClick -bool true

# Trackpad: swipe between pages with three fingers
defaults write NSGlobalDomain AppleEnableSwipeNavigateWithScrolls -bool true
defaults -currentHost write NSGlobalDomain com.apple.trackpad.threeFingerHorizSwipeGesture -int 1
defaults write com.apple.driver.AppleBluetoothMultitouch.trackpad TrackpadThreeFingerHorizSwipeGesture -int 1

# Disable “natural” (Lion-style) scrolling
defaults write NSGlobalDomain com.apple.swipescrolldirection -bool false

# Enable full keyboard access for all controls
# (e.g. enable Tab in modal dialogs)
defaults write NSGlobalDomain AppleKeyboardUIMode -int 3

# Use scroll gesture with the Ctrl (^) modifier key to zoom
defaults write com.apple.universalaccess closeViewScrollWheelToggle -bool true
defaults write com.apple.universalaccess HIDScrollZoomModifierMask -int 262144
# Follow the keyboard focus while zoomed in
defaults write com.apple.universalaccess closeViewZoomFollowsFocus -bool true

# Disable press-and-hold for keys in favor of key repeat
defaults write NSGlobalDomain ApplePressAndHoldEnabled -bool false

# Set a blazingly fast keyboard repeat rate
defaults write NSGlobalDomain KeyRepeat -int 1
defaults write NSGlobalDomain InitialKeyRepeat -int 10

# Set language and text formats
# Note: if you’re in the US, replace `EUR` with `USD`, `Centimeters` with
# `Inches`, `en_GB` with `en_US`, and `true` with `false`.
defaults write NSGlobalDomain AppleLanguages -array "en" "fr"
defaults write NSGlobalDomain AppleLocale -string "en_GB@currency=EUR"
defaults write NSGlobalDomain AppleMeasurementUnits -string "Centimeters"
defaults write NSGlobalDomain AppleMetricUnits -bool true

# Show language menu in the top right corner of the boot screen
sudo defaults write /Library/Preferences/com.apple.loginwindow showInputMenu -bool true

# Set the timezone; see `sudo systemsetup -listtimezones` for other values
sudo systemsetup -settimezone "Europe/Paris" > /dev/null
sudo systemsetup -setnetworktimeserver "time.euro.apple.com"
sudo systemsetup -setusingnetworktime on

# Do not set timezone automatticaly depending on location.
sudo defaults write /Library/Preferences/com.apple.timezone.auto.plist Active -bool false

# Enable 24 hour time.
defaults write com.apple.menuextra.clock DateFormat -string "EEE d MMM HH:mm"


###############################################################################
# Energy saving                                                               #
###############################################################################

# Turns on lid wakeup
sudo pmset -a lidwake 1

# Automatic restart on power loss
sudo pmset -a autorestart 1

# Restart automatically if the computer freezes
sudo systemsetup -setrestartfreeze on

# Sets displaysleep to 10 minutes
sudo pmset -a displaysleep 10

# Do not allow machine to sleep on charger
sudo pmset -c sleep 0

# Set machine sleep to 5 minutes on battery
sudo pmset -b sleep 5

# Set standby delay to default 1 hour
# See: https://www.ewal.net/2012/09/09/slow-wake-for-macbook-pro-retina/
sudo pmset -a standbydelay 3600

# Never go into computer sleep mode
#sudo systemsetup -setcomputersleep Off > /dev/null

# Hibernation mode
# 0: Disable hibernation (speeds up entering sleep mode)
# 3: Copy RAM to disk so the system state can still be restored in case of a
#    power failure.
sudo pmset -a hibernatemode 3

# Remove the sleep image file to save disk space
#sudo rm /private/var/vm/sleepimage
# Create a zero-byte file instead…
#sudo touch /private/var/vm/sleepimage
# …and make sure it can’t be rewritten
#sudo chflags uchg /private/var/vm/sleepimage


###############################################################################
# Screen                                                                      #
###############################################################################

# Save screenshots to the desktop
defaults write com.apple.screencapture location -string "${HOME}/Desktop"

# Save screenshots in PNG format (other options: BMP, GIF, JPG, PDF, TIFF)
defaults write com.apple.screencapture type -string "png"

# Disable shadow in screenshots
defaults write com.apple.screencapture disable-shadow -bool true



###############################################################################
# Nightlight                                                                  #
###############################################################################

# Start night shift from sunset to sunrise
nightlight schedule start


###############################################################################
# MonitorControl.app                                                          #
###############################################################################

# Only affects brightness, not contrast
defaults write me.guillaumeb.MonitorControl lowerContrast -bool false
defaults write me.guillaumeb.MonitorControl showContrast -bool false

# Do not modify all screens at once
defaults write me.guillaumeb.MonitorControl allScreens -bool false


###############################################################################
# Screen Saver                                                                #
###############################################################################

# Start screen saver after 10 minutes
# (mSCP: system_settings_screensaver_timeout_enforce)
defaults -currentHost write com.apple.screensaver idleTime -int 600

# Require password immediately after sleep or screen saver begins. The old
# com.apple.screensaver askForPassword keys are ignored since Big Sur:
# sysadminctl is the supported CLI, and prompts for the user's password
# (mSCP: system_settings_screensaver_password_enforce).
sysadminctl -screenLock immediate -password -

# Screen Saver: Aerial
defaults -currentHost write com.apple.screensaver moduleDict -dict moduleName -string "Aerial" path -string "${HOME}/Library/Screen Savers/Aerial.saver" type -int 0


###############################################################################
# Aerial                                                                      #
###############################################################################

# Disable setup walkthrough
defaults write ~/Library/Containers/com.apple.ScreenSaver.Engine.legacyScreenSaver/Data/Library/Preferences/ByHost/com.JohnCoates.Aerial.plist \
    firstTimeSetup -int 1

# Disable fade in/out
defaults write ~/Library/Containers/com.apple.ScreenSaver.Engine.legacyScreenSaver/Data/Library/Preferences/ByHost/com.JohnCoates.Aerial.plist \
    fadeMode -int 0

# Video format: 4K HEVC
defaults write ~/Library/Containers/com.apple.ScreenSaver.Engine.legacyScreenSaver/Data/Library/Preferences/ByHost/com.JohnCoates.Aerial.plist \
    intVideoFormat -int 3

# Disable if battery < 20%
defaults write ~/Library/Containers/com.apple.ScreenSaver.Engine.legacyScreenSaver/Data/Library/Preferences/ByHost/com.JohnCoates.Aerial.plist \
    intOnBatteryMode -int 2

# Viewing mode: Cloned
defaults write ~/Library/Containers/com.apple.ScreenSaver.Engine.legacyScreenSaver/Data/Library/Preferences/ByHost/com.JohnCoates.Aerial.plist \
    newViewingMode -int 1

# Aligns scenes with system dark mode
defaults write ~/Library/Containers/com.apple.ScreenSaver.Engine.legacyScreenSaver/Data/Library/Preferences/ByHost/com.JohnCoates.Aerial.plist \
    timeMode -int 3

# Enable dynamic rotation of cache
defaults write ~/Library/Containers/com.apple.ScreenSaver.Engine.legacyScreenSaver/Data/Library/Preferences/ByHost/com.JohnCoates.Aerial.plist \
    enableManagement -int 1

# Rotate cache every month
defaults write ~/Library/Containers/com.apple.ScreenSaver.Engine.legacyScreenSaver/Data/Library/Preferences/ByHost/com.JohnCoates.Aerial.plist \
    intCachePeriodicity -int 2

# Limit cache to 20 Gb
defaults write ~/Library/Containers/com.apple.ScreenSaver.Engine.legacyScreenSaver/Data/Library/Preferences/ByHost/com.JohnCoates.Aerial.plist \
    cacheLimit -int 20

# Show download progress on screen saver
defaults write ~/Library/Containers/com.apple.ScreenSaver.Engine.legacyScreenSaver/Data/Library/Preferences/ByHost/com.JohnCoates.Aerial.plist \
    showBackgroundDownloads -int 1

# Deactivate debug mode and logs
defaults write ~/Library/Containers/com.apple.ScreenSaver.Engine.legacyScreenSaver/Data/Library/Preferences/ByHost/com.JohnCoates.Aerial.plist \
    debugMode -bool false

# Aerial layer widget configuration is a serialized JSON string. This hack will
# only allows preferences to be accounted for if all keys of a widget conf are
# present. See: https://github.com/JohnCoates/Aerial/issues/976

# Only shows clock on main displays, without seconds or am/pm
defaults write ~/Library/Containers/com.apple.ScreenSaver.Engine.legacyScreenSaver/Data/Library/Preferences/ByHost/com.JohnCoates.Aerial.plist \
    LayerClock -string \
    '{
        "isEnabled": true,
        "displays": 1,
        "showSeconds": false,
        "hideAmPm": true,
        "clockFormat" : 1,
        "corner" : 3,
        "fontName" : "Helvetica Neue Medium",
        "fontSize" : 50
    }'

# Only shows location for 10 seconds on main display only
defaults write ~/Library/Containers/com.apple.ScreenSaver.Engine.legacyScreenSaver/Data/Library/Preferences/ByHost/com.JohnCoates.Aerial.plist \
    LayerLocation -string \
    '{
        "isEnabled": true,
        "displays": 1,
        "time": 1,
        "corner" : 7,
        "fontName" : "Helvetica Neue Medium",
        "fontSize" : 28
    }'

# Shows date on main display only
defaults write ~/Library/Containers/com.apple.ScreenSaver.Engine.legacyScreenSaver/Data/Library/Preferences/ByHost/com.JohnCoates.Aerial.plist \
    LayerDate -string \
    '{
        "isEnabled": true,
        "displays": 1,
        "format": 0,
        "withYear": true,
        "corner": 3,
        "fontName": "Helvetica Neue Thin",
        "fontSize": 25
    }'


###############################################################################
# Finder                                                                      #
###############################################################################

# Hide all desktop icons (useful when presenting)
defaults write com.apple.finder CreateDesktop -bool false

# Finder: allow quitting via ⌘ + Q; doing so will also hide desktop icons
defaults write com.apple.finder QuitMenuItem -bool true

# Finder: disable window animations and Get Info animations
defaults write com.apple.finder DisableAllAnimations -bool true

# Set ${HOME} as the default location for new Finder windows
# Computer     : `PfCm`
# Volume       : `PfVo`
# $HOME        : `PfHm`
# Desktop      : `PfDe`
# Documents    : `PfDo`
# All My Files : `PfAF`
# Other…       : `PfLo`
defaults write com.apple.finder NewWindowTarget -string "PfHm"
defaults write com.apple.finder NewWindowTargetPath -string "file://${HOME}/"

# Don't show icons for hard drives, servers, and removable media on the desktop
defaults write com.apple.finder ShowExternalHardDrivesOnDesktop -bool false
defaults write com.apple.finder ShowHardDrivesOnDesktop -bool false
defaults write com.apple.finder ShowMountedServersOnDesktop -bool false
defaults write com.apple.finder ShowRemovableMediaOnDesktop -bool false

# Finder: show hidden files by default
defaults write com.apple.finder AppleShowAllFiles -bool true

# Finder: show all filename extensions
defaults write NSGlobalDomain AppleShowAllExtensions -bool true

# Finder: show status bar
defaults write com.apple.finder ShowStatusBar -bool true

# Finder: show path bar
defaults write com.apple.finder ShowPathbar -bool true

# Display full POSIX path as Finder window title
defaults write com.apple.finder _FXShowPosixPathInTitle -bool true

# Customize toolbar
defaults write com.apple.finder "NSToolbar Configuration Browser" '{ "TB Item Identifiers" = ( "com.apple.finder.BACK", "com.apple.finder.PATH", "com.apple.finder.SWCH", "com.apple.finder.ARNG", "NSToolbarFlexibleSpaceItem", "com.apple.finder.SRCH", "com.apple.finder.ACTN" ); "TB Display Mode" = 2; }'

# Keep folders on top when sorting by name
defaults write com.apple.finder _FXSortFoldersFirst -bool true

# When performing a search, search the current folder by default
defaults write com.apple.finder FXDefaultSearchScope -string "SCcf"

# Disable the warning when changing a file extension
defaults write com.apple.finder FXEnableExtensionChangeWarning -bool false

# Enable spring loading for directories
defaults write NSGlobalDomain com.apple.springing.enabled -bool true

# Remove the spring loading delay for directories
defaults write NSGlobalDomain com.apple.springing.delay -float 0

# Avoid creating .DS_Store files on network or USB volumes
defaults write com.apple.desktopservices DSDontWriteNetworkStores -bool true
defaults write com.apple.desktopservices DSDontWriteUSBStores -bool true

# Disable disk image verification
#defaults write com.apple.frameworks.diskimages skip-verify -bool true
#defaults write com.apple.frameworks.diskimages skip-verify-locked -bool true
#defaults write com.apple.frameworks.diskimages skip-verify-remote -bool true

# Automatically open a new Finder window when a volume is mounted
defaults write com.apple.frameworks.diskimages auto-open-ro-root -bool false
defaults write com.apple.frameworks.diskimages auto-open-rw-root -bool false
defaults write com.apple.finder OpenWindowForNewRemovableDisk -bool false

# Set icon view settings on desktop and in icon views
for view ('Desktop' 'FK_Standard' 'Standard'); do
    # Show item info near icons on the desktop and in other icon views
    # Show item info to the right of the icons on the desktop
    # Enable snap-to-grid for icons on the desktop and in other icon views
    # Increase grid spacing for icons on the desktop and in other icon views
    # Increase the size of icons on the desktop and in other icon views
    /usr/libexec/PlistBuddy \
        -c "Set :${view}ViewSettings:IconViewSettings:showItemInfo  true"  \
        -c "Set :${view}ViewSettings:IconViewSettings:labelOnBottom false" \
        -c "Set :${view}ViewSettings:IconViewSettings:arrangeBy     grid"  \
        -c "Set :${view}ViewSettings:IconViewSettings:gridSpacing   100"   \
        -c "Set :${view}ViewSettings:IconViewSettings:iconSize      32"    \
        ~/Library/Preferences/com.apple.finder.plist
done

# Use list view in all Finder windows by default
# Four-letter codes for the other view modes:
# Icon View   : `icnv`
# List View   : `Nlsv`
# Column View : `clmv`
# Gallery View: `glyv`
defaults write com.apple.finder FXPreferredViewStyle -string "Nlsv"
# After configuring preferred view style, clear all `.DS_Store` files
# to ensure settings are applied for every directory
sudo command find / -name ".DS_Store" -print -delete || true

# View Options
# ColumnShowIcons    : Show preview column
# ShowPreview        : Show icons
# ShowIconThumbnails : Show icon preview
# ArrangeBy          : Sort by
#   dnam : Name
#   kipl : Kind
#   ludt : Date Last Opened
#   pAdd : Date Added
#   modd : Date Modified
#   ascd : Date Created
#   logs : Size
#   labl : Tags
/usr/libexec/PlistBuddy \
    -c "Delete :StandardViewOptions:ColumnViewOptions:ColumnShowIcons"    \
    -c "Delete :StandardViewOptions:ColumnViewOptions:FontSize"           \
    -c "Delete :StandardViewOptions:ColumnViewOptions:ShowPreview"        \
    -c "Delete :StandardViewOptions:ColumnViewOptions:ShowIconThumbnails" \
    -c "Delete :StandardViewOptions:ColumnViewOptions:ArrangeBy"          \
    ~/Library/Preferences/com.apple.finder.plist || true
/usr/libexec/PlistBuddy \
    -c "Add :StandardViewOptions:ColumnViewOptions:ColumnShowIcons    bool    true" \
    -c "Add :StandardViewOptions:ColumnViewOptions:FontSize           integer 11"   \
    -c "Add :StandardViewOptions:ColumnViewOptions:ShowPreview        bool    true" \
    -c "Add :StandardViewOptions:ColumnViewOptions:ShowIconThumbnails bool    true" \
    -c "Add :StandardViewOptions:ColumnViewOptions:ArrangeBy          string  dnam" \
    ~/Library/Preferences/com.apple.finder.plist

# Disable the warning before emptying the Trash
defaults write com.apple.finder WarnOnEmptyTrash -bool false

# Enable AirDrop over Ethernet and on unsupported Macs running Lion
defaults write com.apple.NetworkBrowser BrowseAllInterfaces -bool true

# Enable the MacBook Air SuperDrive on any Mac
#sudo nvram boot-args="mbasd=1"

# Show the ~/Library folder
chflags nohidden "${HOME}/Library" && xattr -d com.apple.FinderInfo "${HOME}/Library" 2> /dev/null || true

# Show the /Volumes folder
sudo chflags nohidden /Volumes

# Expand the following File Info panes:
# “General”, “Open with”, and “Sharing & Permissions”
defaults write com.apple.finder FXInfoPanesExpanded -dict \
    General -bool true \
    OpenWith -bool true \
    Privileges -bool true

# Prefer tabs when opening documents
defaults write -globalDomain "AppleWindowTabbingMode" -string "always"

# Copy window location: top right (as if it is a notification)
defaults write com.apple.finder CopyProgressWindowLocation -string "{2160, 23}"


###############################################################################
# Sets applications as default handlers for file types and URL schemes        #
###############################################################################
# Associations live in ~/.config/infat/config.toml (symlinked from this repo by
# install.sh) and are applied here through LaunchServices by infat:
#   https://github.com/philocalyst/infat
#
# On recent macOS (26.4+) LaunchServices may prompt to confirm each change, and
# the default browser prompts on every version. A missing app or a declined
# prompt must not abort the script, hence the "|| true".
if command -v infat &> /dev/null; then
    infat --config "${HOME}/.config/infat/config.toml" || true
fi


###############################################################################
# iCloud                                                                      #
###############################################################################

# Save to disk (not to iCloud) by default
defaults write NSGlobalDomain NSDocumentSaveNewDocumentsToCloud -bool false

# Show warning before removing from iCloud Drive
defaults write com.apple.finder FXEnableRemoveFromICloudDriveWarning -bool false

# Allow Handoff between this Mac and your iCloud devices
defaults -currentHost write com.apple.coreservices.useractivityd "ActivityAdvertisingAllowed" -bool true
defaults -currentHost write com.apple.coreservices.useractivityd "ActivityReceivingAllowed" -bool true

# Sync Downloads folders to iCloud
# sudo rm -rf ~/Downloads/
# ln -s ~/Library/Mobile\ Documents/com~apple~CloudDocs/Downloads/ ~/Downloads

# Add an iCloud shortcut in home root.
ln -f -s ~/Library/Mobile\ Documents/com~apple~CloudDocs ~/iCloud

###############################################################################
# Dock and hot corners                                                        #
###############################################################################

# Enable highlight hover effect for the grid view of a stack (Dock)
defaults write com.apple.dock mouse-over-hilite-stack -bool true

# Set the icon size of Dock items to 36 pixels
defaults write com.apple.dock tilesize -int 52

# Enable magnification
defaults write com.apple.dock "magnification" -bool true
defaults write com.apple.dock "largesize" -int 90

# Change minimize/maximize window effect ("scale" or "genie")
defaults write com.apple.dock mineffect -string "genie"

# Minimize windows into their application’s icon
defaults write com.apple.dock minimize-to-application -bool true

# Enable spring loading for all Dock items
defaults write com.apple.dock enable-spring-load-actions-on-all-items -bool true

# Show indicator lights for open applications in the Dock
defaults write com.apple.dock show-process-indicators -bool true

# Wipe all (default) app icons from the Dock
# This is only really useful when setting up a new Mac, or if you don’t use
# the Dock to launch apps.
#defaults write com.apple.dock persistent-apps -array

# Do not only show open applications in the Dock
defaults write com.apple.dock static-only -bool false

# Don't show recent applications in the dock
defaults write com.apple.dock show-recents -bool true

# Don’t animate opening applications from the Dock
defaults write com.apple.dock launchanim -bool true

# Speed up Mission Control animations
defaults write com.apple.dock expose-animation-duration -float 0.1

# Don’t group windows by application in Mission Control
# (i.e. use the old Exposé behavior instead)
#defaults write com.apple.dock expose-group-by-app -bool false

# Don’t automatically rearrange Spaces based on most recent use
defaults write com.apple.dock mru-spaces -bool false

# Remove the auto-hiding Dock delay
defaults write com.apple.dock autohide-delay -int 0
# Remove the animation when hiding/showing the Dock
defaults write com.apple.dock autohide-time-modifier -int 0

# Automatically hide and show the Dock
defaults write com.apple.dock autohide -bool true

# Make Dock icons of hidden applications translucent
defaults write com.apple.dock showhidden -bool true

# Disable the Launchpad gesture (pinch with thumb and three fingers)
#defaults write com.apple.dock showLaunchpadGestureEnabled -int 0

# Make the cmd-tab app switcher show up on all monitors.
#defaults write com.apple.Dock appswitcher-all-displays -bool true

# Reset Launchpad, but keep the desktop wallpaper intact
command find "${HOME}/Library/Application Support/Dock" -maxdepth 1 -name "*-*.db" -delete

# Add iOS & Watch Simulator to Launchpad
#sudo ln -sf "/Applications/Xcode.app/Contents/Developer/Applications/Simulator.app" "/Applications/Simulator.app"
#sudo ln -sf "/Applications/Xcode.app/Contents/Developer/Applications/Simulator (Watch).app" "/Applications/Simulator (Watch).app"

# Add a spacer to the left side of the Dock (where the applications are)
#defaults write com.apple.dock persistent-apps -array-add '{tile-data={}; tile-type="spacer-tile";}'
# Add a spacer to the right side of the Dock (where the Trash is)
#defaults write com.apple.dock persistent-others -array-add '{tile-data={}; tile-type="spacer-tile";}'

# Hot corners
# Possible values:
#  0: no-op
#  2: Mission Control
#  3: Show application windows
#  4: Desktop
#  5: Start screen saver
#  6: Disable screen saver
# 10: Put display to sleep
# 11: Launchpad
# 12: Notification Center
# Top left screen corner → Start screen saver
defaults write com.apple.dock wvous-tl-corner -int 5
defaults write com.apple.dock wvous-tl-modifier -int 0

# Remove apps I don't use from the dock.
for shortcut_label (
    "Contacts"
    "FaceTime"
    "Launchpad"
    "Mail"
    "Maps"
    "Photos"
    "Podcasts"
    "Reminders"
    "TV"
); do
    dockutil --remove "${shortcut_label}" --allhomes --no-restart
done

# Add new app shortcuts to the dock.
for app (
    "Proton Pass"
    "Fork"
    "Home"
    "LibreOffice"
    "NetNewsWire"
    "Signal"
    "Tor Browser"
    "Transmission"
    "Visual Studio Code"
); do
    if [[ $(dockutil --find "${app}" > /dev/null; echo $?) -ne 0 ]]; then
        dockutil --add "/Applications/${app}.app" --replacing "${app}" --no-restart
    fi
done


###############################################################################
# Safari & WebKit                                                             #
###############################################################################

# Privacy: don’t send search queries to Apple
defaults write com.apple.Safari UniversalSearchEnabled -bool false
defaults write com.apple.Safari SuppressSearchSuggestions -bool true

# Configure DuckDuckGo as main search engine
defaults write com.apple.Safari SearchProviderIdentifier -string "com.duckduckgo"
defaults write NSGlobalDomain NSProviderIdentifier -string "com.duckduckgo"

# Press Tab to highlight each item on a web page
defaults write com.apple.Safari WebKitPreferences.tabFocusesLinks -bool true

# Show the full URL in the address bar (note: this still hides the scheme)
defaults write com.apple.Safari ShowFullURLInSmartSearchField -bool true

# Safari > General > Safari opens with:
# false,false: A new window
# false,true: A new private window
# true, false: All windows from last session
defaults write com.apple.Safari AlwaysRestoreSessionAtLaunch -bool true
defaults write com.apple.Safari OpenPrivateWindowWhenNotRestoringSessionAtLaunch -bool false

# Setup new window and tab behavior
# 0: Homepage
# 1: Empty Page
# 2: Same Page
# 4: Start Page
defaults write com.apple.Safari NewTabBehavior -int 4
defaults write com.apple.Safari NewWindowBehavior -int 4

# Number of top sites to show:
# 6 top sites: 0
# 12 top sites: 1
# 24 top sites: 2
defaults write com.apple.Safari TopSitesGridArrangement -int 0

# Open pages in tabs instead of windows:
# 0: Never
# 1: Automatically
# 2: Always
defaults write com.apple.Safari TabCreationPolicy -int 2

# Set tab bar visibility
defaults write com.apple.Safari AlwaysShowTabBar -bool false

# cmd+click opens a link in a new tab
defaults write com.apple.Safari CommandClickMakesTabs -bool true

# When a new tab or window opens, make it active
defaults write com.apple.Safari OpenNewTabsInFront -bool false

# Use cmd+1 through cmd+9 to switch tabs
defaults write com.apple.Safari Command1Through9SwitchesTabs -bool true

# Set Safari’s home page to `about:blank` for faster loading
defaults write com.apple.Safari HomePage -string ""

# Save downloaded files to
defaults write com.apple.Safari DownloadsPath -string '~/Library/Mobile Documents/com~apple~CloudDocs/Downloads'

# Prevent Safari from opening ‘safe’ files automatically after downloading
defaults write com.apple.Safari AutoOpenSafeDownloads -bool false

# Save format
# 0: Page Source
# 1: Web Archive
defaults write com.apple.Safari SavePanelFileFormat -int 0

# Hide Safari’s bookmarks bar by default
defaults write com.apple.Safari ShowFavoritesBar -bool false
defaults write com.apple.Safari ShowFavoritesBar-v2 -bool false

# Show status bar
defaults write com.apple.Safari ShowStatusBar -bool true
defaults write com.apple.Safari ShowOverlayStatusBar -bool true
defaults write com.apple.Safari ShowStatusBarInFullScreen -bool true

# Always show toolbar in full screen
defaults write com.apple.Safari AutoShowToolbarInFullScreen -bool false

# Show Favorites under Smart Search field
defaults write com.apple.Safari ShowFavoritesUnderSmartSearchField -bool false

# Show Safari’s sidebar in new windows
defaults write com.apple.Safari ShowSidebarInNewWindows -bool true

# Show Safari’s sidebar in Top Sites
defaults write com.apple.Safari ShowSidebarInTopSites -bool true

# Show Sidebar Mode
# Values: "Bookmarks", "Reading List"
defaults write com.apple.Safari SidebarViewModeIdentifier -string  "Bookmarks"

# Preload Top Hit in the background
defaults write com.apple.Safari PreloadTopHit -bool false

# Make Safari’s search banners default to Contains instead of Starts With
defaults write com.apple.Safari FindOnPageMatchesWordStartsOnly -bool false

# Remove useless icons from Safari’s bookmarks bar
defaults write com.apple.Safari ProxiesInBookmarksBar "()"

# Don't show frequently visited sites in Top bar
defaults write com.apple.SafariTechnologyPreview ShowFrequentlyVisitedSites -bool false

# Save article for offline reading automatically.
defaults write com.apple.Safari ReadingListSaveArticlesOfflineAutomatically -bool true

# Enable the Develop menu and the Web Inspector in Safari.
# Source: https://apple.stackexchange.com/a/429820
defaults write com.apple.Safari.SandboxBroker ShowDevelopMenu -bool true
defaults write com.apple.Safari IncludeDevelopMenu -bool true
defaults write com.apple.Safari WebKitDeveloperExtrasEnabledPreferenceKey -bool true

# Add a context menu item for showing the Web Inspector in web views.
# Source: https://blog.jim-nielsen.com/2022/inspecting-web-views-in-macos/
defaults write NSGlobalDomain WebKitDeveloperExtras -bool true
defaults write -g WebKitDeveloperExtras -bool YES
# Enable Safari’s debug menu
defaults write com.apple.Safari IncludeInternalDebugMenu -bool true

# Set default encoding
defaults write com.apple.Safari WebKitDefaultTextEncodingName -string 'utf-8'
defaults write com.apple.Safari WebKitPreferences.defaultTextEncodingName -string 'utf-8'

# Enable continuous spellchecking
defaults write com.apple.Safari WebContinuousSpellCheckingEnabled -bool true
# Disable auto-correct
defaults write com.apple.Safari WebAutomaticSpellingCorrectionEnabled -bool false

# Disable AutoFill
defaults write com.apple.Safari AutoFillPasswords -bool false
defaults write com.apple.Safari AutoFillFromAddressBook -bool false
defaults write com.apple.Safari AutoFillCreditCardData -bool false
defaults write com.apple.Safari AutoFillMiscellaneousForms -bool false

# Warn about fraudulent websites
defaults write com.apple.Safari WarnAboutFraudulentWebsites -bool true

# Enable JavaScript
# defaults write com.apple.Safari WebKitJavaScriptEnabled -bool true
# defaults write com.apple.Safari com.apple.Safari.ContentPageGroupIdentifier.WebKit2JavaScriptEnabled -bool true

# Block pop-up windows
defaults write com.apple.Safari WebKitJavaScriptCanOpenWindowsAutomatically -bool false
defaults write com.apple.Safari com.apple.Safari.ContentPageGroupIdentifier.WebKit2JavaScriptCanOpenWindowsAutomatically -bool false

# Disable auto-playing video
defaults write com.apple.Safari WebKitMediaPlaybackAllowsInline -bool false
defaults write com.apple.SafariTechnologyPreview WebKitMediaPlaybackAllowsInline -bool false
defaults write com.apple.Safari com.apple.Safari.ContentPageGroupIdentifier.WebKit2AllowsInlineMediaPlayback -bool false
defaults write com.apple.SafariTechnologyPreview com.apple.Safari.ContentPageGroupIdentifier.WebKit2AllowsInlineMediaPlayback -bool false

# Allow WebGL
# defaults write com.apple.Safari com.apple.Safari.ContentPageGroupIdentifier.WebKit2WebGLEnabled -bool true

# Enable extensions
defaults write com.apple.Safari ExtensionsEnabled -bool true

# Update extensions automatically
defaults write com.apple.Safari InstallExtensionUpdatesAutomatically -bool true

# Cookies and website data:
# 0,2,2: Always block
# 3,1,1: Allow from current website only
# 2,1,1: Allow from websites I visit
# 1,0,0: Always allow
defaults write com.apple.Safari BlockStoragePolicy -int 2
defaults write com.apple.Safari WebKitStorageBlockingPolicy -int 1
defaults write com.apple.Safari com.apple.Safari.ContentPageGroupIdentifier.WebKit2StorageBlockingPolicy -int 1

# Prevent cross-site tracking, completing the legacy pair above with the
# modern WebKit key (mSCP: os_safari_prevent_cross-site_tracking_enable).
defaults write com.apple.Safari WebKitPreferences.storageBlockingPolicy -int 1

# Use privacy-preserving click measurement instead of ad tracking
# (mSCP: os_safari_advertising_privacy_protection_enable).
defaults write com.apple.Safari WebKitPreferences.privateClickMeasurementEnabled -bool true

# Deny location services access from websites
# 0: Deny without Prompting
# 1: Prompt for each website once each day
# 2: Prompt for each website one time only
defaults write com.apple.Safari SafariGeolocationPermissionPolicy -int 0

# Allow websites to ask for permission to send push notifications
defaults write com.apple.Safari CanPromptForPushNotifications -bool false

# Remove downloads list items
# 0: Manually
# 1: When Safari Quits
# 2: Upon Successful Download
defaults write com.apple.Safari DownloadsClearingPolicy -int 2

# Clear history:
# 1 = after one day
# 7 = after one week
# 14 = after two weeks
# 31 = after one month
# 365 = after one year
# 365000 = never (after 1000 years)
defaults write com.apple.Safari HistoryAgeInDaysLimit -int 14

# Don't allow apple pay checking.
defaults write com.apple.Safari com.apple.Safari.ContentPageGroupIdentifier.WebKit2ApplePayCapabilityDisclosureAllowed -bool false

# Disable website specific search.
defaults write com.apple.Safari WebsiteSpecificSearchEnabled -bool false

# Never use font sizes smaller than
defaults write com.apple.Safari WebKitMinimumFontSize -int 9
defaults write com.apple.Safari WebKitPreferences.minimumFontSize -int 9

# Print headers and footers
defaults write com.apple.Safari PrintHeadersAndFooters -bool false

# Print backgrounds
defaults write com.apple.Safari WebKitShouldPrintBackgroundsPreferenceKey -bool false
defaults write com.apple.Safari "com.apple.Safari.ContentPageGroupIdentifier.WebKit2ShouldPrintBackgrounds" -bool false


###############################################################################
# Mail                                                                        #
###############################################################################

# Disable send and reply animations in Mail.app
defaults write com.apple.mail DisableReplyAnimations -bool true
defaults write com.apple.mail DisableSendAnimations -bool true

# Copy email addresses as `foo@example.com` instead of `Foo Bar <foo@example.com>` in Mail.app
defaults write com.apple.mail AddressesIncludeNameOnPasteboard -bool false

# Add the keyboard shortcut ⌘ + Enter to send an email in Mail.app
defaults write com.apple.mail NSUserKeyEquivalents -dict-add "Send" "@\U21a9"

# Display emails in threaded mode, sorted by date (oldest at the top)
defaults write com.apple.mail DraftsViewerAttributes -dict-add "DisplayInThreadedMode" -string "yes"
defaults write com.apple.mail DraftsViewerAttributes -dict-add "SortedDescending" -string "yes"
defaults write com.apple.mail DraftsViewerAttributes -dict-add "SortOrder" -string "received-date"

# Disable inline attachments (just show the icons)
defaults write com.apple.mail DisableInlineAttachmentViewing -bool true

# Disable automatic spell checking
defaults write com.apple.mail SpellCheckingBehavior -string "NoSpellCheckingEnabled"

# Show To/Cc label in message list
defaults write com.apple.mail EnableToCcInMessageList -bool true


###############################################################################
# iWork                                                                       #
###############################################################################

## Keynote

#defaults write com.apple.iWork.Keynote 'ShowStartingPointsForNewDocument' -bool false
defaults write com.apple.iWork.Keynote 'dontShowWhatsNew' -bool true
defaults write com.apple.iWork.Keynote 'FirstRunFlag' -bool true

## Numbers

#defaults write com.apple.iWork.Numbers 'ShowStartingPointsForNewDocument' -bool false
defaults write com.apple.iWork.Numbers 'dontShowWhatsNew' -bool true
defaults write com.apple.iWork.Numbers 'FirstRunFlag' -bool true

## Pages

#defaults write com.apple.iWork.Pages 'ShowStartingPointsForNewDocument' -bool false
defaults write com.apple.iWork.Pages 'dontShowWhatsNew' -bool true
defaults write com.apple.iWork.Pages 'FirstRunFlag' -bool true


###############################################################################
# Spotlight                                                                   #
###############################################################################

# Hide Spotlight tray-icon (and subsequent helper)
sudo chmod 600 /System/Library/CoreServices/Search.bundle/Contents/MacOS/Search || true

# Disable Spotlight indexing for any volume that gets mounted and has not yet
# been indexed before.
# Source: https://mattprice.me/2020/programmatically-modify-spotlight-ignore/
sudo mdutil -i off "/Volumes"
sudo /usr/libexec/PlistBuddy -c "Add :Exclusions: string /Volumes" \
    /System/Volumes/Data/.Spotlight-V100/VolumeConfiguration.plist

# Change indexing order and disable some search results
# Yosemite-specific search results (remove them if you are using macOS 10.9 or older):
#     MENU_DEFINITION
#     MENU_CONVERSION
#     MENU_EXPRESSION
#     MENU_SPOTLIGHT_SUGGESTIONS (send search queries to Apple)
#     MENU_WEBSEARCH             (send search queries to Apple)
#     MENU_OTHER
defaults write com.apple.spotlight orderedItems -array \
    '{"enabled" = 1;"name" = "APPLICATIONS";}' \
    '{"enabled" = 1;"name" = "SYSTEM_PREFS";}' \
    '{"enabled" = 1;"name" = "DIRECTORIES";}' \
    '{"enabled" = 1;"name" = "PDF";}' \
    '{"enabled" = 1;"name" = "FONTS";}' \
    '{"enabled" = 0;"name" = "DOCUMENTS";}' \
    '{"enabled" = 0;"name" = "MESSAGES";}' \
    '{"enabled" = 0;"name" = "CONTACT";}' \
    '{"enabled" = 0;"name" = "EVENT_TODO";}' \
    '{"enabled" = 0;"name" = "IMAGES";}' \
    '{"enabled" = 0;"name" = "BOOKMARKS";}' \
    '{"enabled" = 0;"name" = "MUSIC";}' \
    '{"enabled" = 0;"name" = "MOVIES";}' \
    '{"enabled" = 0;"name" = "PRESENTATIONS";}' \
    '{"enabled" = 0;"name" = "SPREADSHEETS";}' \
    '{"enabled" = 1;"name" = "SOURCE";}' \
    '{"enabled" = 0;"name" = "MENU_DEFINITION";}' \
    '{"enabled" = 0;"name" = "MENU_OTHER";}' \
    '{"enabled" = 1;"name" = "MENU_CONVERSION";}' \
    '{"enabled" = 1;"name" = "MENU_EXPRESSION";}' \
    '{"enabled" = 0;"name" = "MENU_WEBSEARCH";}' \
    '{"enabled" = 0;"name" = "MENU_SPOTLIGHT_SUGGESTIONS";}'
# Load new settings before rebuilding the index
killall mds &> /dev/null || true
# Make sure indexing is enabled for the main volume
sudo mdutil -i on / > /dev/null
# Rebuild the index from scratch
sudo mdutil -E / > /dev/null



###############################################################################
# Terminal                                                                    #
###############################################################################

# Set Zsh as default shell
sudo chsh -s /bin/zsh $USERNAME
sudo chsh -s /bin/zsh root

# Only use UTF-8 in Terminal.app
defaults write com.apple.terminal StringEncodings -array "4"

# Use specific color scheme and settings in Terminal.app
(
osascript <<EOF
tell application "Terminal"

    local allOpenedWindows
    local initialOpenedWindows
    local windowID
    set themeName to "Monokai Soda"

    (* Store the IDs of all the open terminal windows. *)
    set initialOpenedWindows to id of every window

    (* Open the custom theme so that it gets added to the list
       of available terminal themes (note: this will open two
       additional terminal windows). *)
    do shell script "open './assets/" & themeName & ".terminal'"

    (* Wait a little bit to ensure that the custom theme is added. *)
    delay 1

    (* Set the custom theme as the default terminal theme. *)
    set default settings to settings set themeName

    (* Get the IDs of all the currently opened terminal windows. *)
    set allOpenedWindows to id of every window

    repeat with windowID in allOpenedWindows

        (* Close the additional windows that were opened in order
           to add the custom theme to the list of terminal themes. *)
        if initialOpenedWindows does not contain windowID then
            close (every window whose id is windowID)

        (* Change the theme for the initial opened terminal windows
           to remove the need to close them in order for the custom
           theme to be applied. *)
        else
            set current settings of tabs of (every window whose id is windowID) to settings set themeName
        end if

    end repeat

end tell
EOF
) || true

# Enable “focus follows mouse” for Terminal.app and all X11 apps
# i.e. hover over a window and start typing in it without clicking first
defaults write com.apple.terminal FocusFollowsMouse -bool true
defaults write org.x.X11 wm_ffm -bool true
defaults write org.x.X11 wm_click_through -bool true

# Enable Secure Keyboard Entry in Terminal.app
# See: https://security.stackexchange.com/a/47786/8918
defaults write com.apple.terminal SecureKeyboardEntry -bool true

# Disable the annoying line marks
defaults write com.apple.Terminal ShowLineMarks -int 0

# Audible and Visual Bells
/usr/libexec/PlistBuddy \
    -c "Delete :WindowSettings:Basic:Bell"       \
    -c "Delete :WindowSettings:Basic:VisualBell" \
    ~/Library/Preferences/com.apple.terminal.plist || true
/usr/libexec/PlistBuddy \
    -c "Add    :WindowSettings:Basic:Bell       bool false" \
    -c "Add    :WindowSettings:Basic:VisualBell bool true"  \
    ~/Library/Preferences/com.apple.terminal.plist


###############################################################################
# Time Machine                                                                #
###############################################################################

# Source: https://krypted.com/mac-os-x/ins-outs-using-tmutil-backup-restore-review-time-machine-backups/

# Prevent Time Machine from prompting to use new hard drives as backup volume
defaults write com.apple.TimeMachine DoNotOfferNewDisksForBackup -bool true

# Limit Time Machine total backup size to 1 TB (=1024*1024)
# Source: http://www.defaults-write.com/time-machine-setup-a-size-limit-for-backup-volumes/
sudo defaults write com.apple.TimeMachine MaxSize -integer 1048576

# Exclude Aerial screen saver big video cache.
AERIAL_CACHE="~/Library/Containers/com.apple.ScreenSaver.Engine.legacyScreenSaver/Data/Library/Application Support/Aerial/Cache"
if [[ -f "${AERIAL_CACHE}" ]]; then
    sudo tmutil addexclusion "${AERIAL_CACHE}"
fi

# Activate Time Machine backups (including local snapshots).
sudo tmutil enable

###############################################################################
# Activity Monitor                                                            #
###############################################################################

# Show the main window when launching Activity Monitor
defaults write com.apple.ActivityMonitor OpenMainWindow -bool true

# Show processes in Activity Monitor
# 100: All Processes
# 101: All Processes, Hierarchally
# 102: My Processes
# 103: System Processes
# 104: Other User Processes
# 105: Active Processes
# 106: Inactive Processes
# 106: Inactive Processes
# 107: Windowed Processes
defaults write com.apple.ActivityMonitor ShowCategory -int 100

# Sort Activity Monitor results by CPU usage
defaults write com.apple.ActivityMonitor SortColumn -string "CPUUsage"
defaults write com.apple.ActivityMonitor SortDirection -int 0

# Set columns for each tab
defaults write com.apple.ActivityMonitor "UserColumnsPerTab v5.0" -dict \
    '0' '( Command, CPUUsage, CPUTime, Threads, IdleWakeUps, PID, UID )' \
    '1' '( Command, anonymousMemory, compressedMemory, ResidentSize, PurgeableMem, Threads, Ports, PID, UID)' \
    '2' '( Command, PowerScore, 12HRPower, AppSleep, graphicCard, UID )' \
    '3' '( Command, bytesWritten, bytesRead, Architecture, PID, UID )' \
    '4' '( Command, txBytes, rxBytes, txPackets, rxPackets, PID, UID )'

# Sort columns in each tab
defaults write com.apple.ActivityMonitor UserColumnSortPerTab -dict \
    '0' '{ direction = 0; sort = CPUUsage; }' \
    '1' '{ direction = 0; sort = ResidentSize; }' \
    '2' '{ direction = 0; sort = 12HRPower; }' \
    '3' '{ direction = 0; sort = bytesWritten; }' \
    '4' '{ direction = 0; sort = txBytes; }'

# Update Frequency (in seconds)
# 1: Very often (1 sec)
# 2: Often (2 sec)
# 5: Normally (5 sec)
defaults write com.apple.ActivityMonitor UpdatePeriod -int 2

# Show Data in the Disk graph (instead of IO)
defaults write com.apple.ActivityMonitor DiskGraphType -int 1

# Show Data in the Network graph (instead of packets)
defaults write com.apple.ActivityMonitor NetworkGraphType -int 1

# Visualize CPU usage in the Activity Monitor Dock icon
# 0: Application Icon
# 2: Network Usage
# 3: Disk Activity
# 5: CPU Usage
# 6: CPU History
defaults write com.apple.ActivityMonitor IconType -int 5


###############################################################################
# Quartz Debug                                                                #
###############################################################################

# Lets the window list work.
defaults write com.apple.QuartzDebug QuartzDebugPrivateInterface -bool YES

# Show useful things in the dock icon.
defaults write com.apple.QuartzDebug QDDockShowFramemeterHistory -bool YES
defaults write com.apple.QuartzDebug QDDockShowNumericalFps -bool YES

# Identify which app a window belongs to (press ⌃⌥ while hovering over it).
defaults write com.apple.QuartzDebug QDShowWindowInfoOnMouseOver -bool YES


###############################################################################
# Contacts                                                                    #
###############################################################################

# Enable the debug menu in Address Book
defaults write com.apple.addressbook ABShowDebugMenu -bool true

# Show first name
# false : Before last name
# true  : Following last name
defaults write com.apple.AddressBook ABNameDisplay -bool false

# Sort by
defaults write com.apple.AddressBook ABNameSortingFormat -string "sortingLastName sortingFirstName"

# Short name format
# 0: Full Name
# 1: First Name & Last Initial
# 2: First Initial & Last Name
# 3: First Name Only
# 4: Last Name Only
defaults write com.apple.AddressBook ABShortNameStyle -int 2

# Prefer nicknames
defaults write com.apple.AddressBook ABShortNamePrefersNickname -bool true

# Address format
defaults write com.apple.AddressBook ABDefaultAddressCountryCode -string "us"

# vCard Format
# falsec: 3.0
# true  : 2.1
defaults write com.apple.AddressBook ABUse21vCardFormat -bool false

# Enable private me card
defaults write com.apple.AddressBook ABPrivateVCardFieldsEnabled -bool false

# Export notes in vCards
defaults write com.apple.AddressBook ABIncludeNotesInVCard -bool false

# Export photos in vCards
defaults write com.apple.AddressBook ABIncludePhotosInVCard -bool false

# Show first name:
# 1: Before last name
# 2: Following last name
defaults write NSGlobalDomain NSPersonNameDefaultDisplayNameOrder -int 1

# Prefer nicknames
defaults write NSGlobalDomain NSPersonNameDefaultShouldPreferNicknamesPreference -bool true


###############################################################################
# Calendar                                                                    #
###############################################################################

# Days per week
defaults write com.apple.iCal "n days of week" -int 7

# Start week on:
# 0: Sunday
# 6: Saturday
defaults write com.apple.iCal "first day of week" -int 1

# Scroll in week view by:
# 0: Day
# 1: Week
# 2: Week, Stop on Today
defaults write com.apple.iCal "scroll by weeks in week view" -int 1

# Day starts at:
defaults write com.apple.iCal "first minute of work hours" -int 480

# Day ends at:
defaults write com.apple.iCal "last minute of work hours" -int 1080

# Show X hours at a time
defaults write com.apple.iCal "number of hours displayed" -int 16

# Turn on timezone support
defaults write com.apple.iCal "TimeZone support enabled" -bool true

# Show events in year view
defaults write com.apple.iCal "Show heat map in Year View" -bool true

# Show week numbers
defaults write com.apple.iCal "Show Week Numbers" -bool true

# Open events in separate windows
# defaults write com.apple.iCal OpenEventsInWindowType -bool true

# Ask before sending changes to events
defaults write com.apple.iCal WarnBeforeSendingInvitations -bool true


###############################################################################
# TextEdit and Disk Utility                                                   #
###############################################################################

# Use plain text mode for new TextEdit documents
defaults write com.apple.TextEdit RichText -int 0
# Open and save files as UTF-8 in TextEdit
defaults write com.apple.TextEdit PlainTextEncoding -int 4
defaults write com.apple.TextEdit PlainTextEncodingForWrite -int 4

# Enable the debug menu in Disk Utility
defaults write com.apple.DiskUtility DUDebugMenuEnabled -bool true
defaults write com.apple.DiskUtility advanced-image-options -bool true

# Show All Devices
defaults write com.apple.DiskUtility SidebarShowAllDevices -bool true


###############################################################################
# QuickTime
###############################################################################

# Auto-play videos when opened with QuickTime Player
defaults write com.apple.QuickTimePlayerX MGPlayMovieOnOpen -bool true

# Set recording quality
# High:    MGCompressionPresetHighQuality
# Maximum: MGCompressionPresetMaximumQuality
defaults write com.apple.QuickTimePlayerX MGRecordingCompressionPresetIdentifier -string 'MGCompressionPresetMaximumQuality'

# Show mouse clicks in screen recordings
defaults write com.apple.QuickTimePlayerX MGScreenRecordingDocumentShowMouseClicksUserDefaultsKey -bool true


###############################################################################
# Mac App Store                                                               #
###############################################################################

# Enable the WebKit Developer Tools in the Mac App Store
defaults write com.apple.appstore WebKitDeveloperExtras -bool true

# Enable Debug Menu in the Mac App Store
defaults write com.apple.appstore ShowDebugMenu -bool true

# Turn on automatic checking for updates
sudo softwareupdate --schedule on

# softwareupdated reads its settings from the system domain: user-domain
# writes to com.apple.SoftwareUpdate are ignored.
# Enable the automatic update check
sudo defaults write /Library/Preferences/com.apple.SoftwareUpdate AutomaticCheckEnabled -bool true

# Download newly available updates in background
# (mSCP: system_settings_software_update_download_enforce)
sudo defaults write /Library/Preferences/com.apple.SoftwareUpdate AutomaticDownload -bool true

# Install security responses and system data files (mSCP:
# system_settings_critical_update_install_enforce / os_config_data_install_enforce)
sudo defaults write /Library/Preferences/com.apple.SoftwareUpdate CriticalUpdateInstall -bool true
sudo defaults write /Library/Preferences/com.apple.SoftwareUpdate ConfigDataInstall -bool true

# Install macOS updates automatically
# (mSCP: system_settings_install_macos_updates_enforce)
sudo defaults write /Library/Preferences/com.apple.SoftwareUpdate AutomaticallyInstallMacOSUpdates -bool true

# Turn on App Store app auto-update (mSCP: os_software_update_app_update_enforce)
sudo defaults write /Library/Preferences/com.apple.SoftwareUpdate AutomaticallyInstallAppUpdates -bool true
sudo defaults write /Library/Preferences/com.apple.commerce AutoUpdate -bool true

# Turn off video autoplay.
defaults write com.apple.AppStore AutoPlayVideoSetting -string "off"
defaults write com.apple.AppStore UserSetAutoPlayVideoSetting -int 1


###############################################################################
# Photos                                                                      #
###############################################################################

# Prevent Photos from opening automatically when devices are plugged in
defaults -currentHost write com.apple.ImageCapture disableHotPlug -bool true


###############################################################################
# Messages                                                                    #
###############################################################################

# Disable automatic emoji substitution (i.e. use plain text smileys)
defaults write com.apple.messageshelper.MessageController SOInputLineSettings -dict-add "automaticEmojiSubstitutionEnablediMessage" -bool false

# Disable smart quotes as it’s annoying for messages that contain code
defaults write com.apple.messageshelper.MessageController SOInputLineSettings -dict-add "automaticQuoteSubstitutionEnabled" -bool false

# Disable continuous spell checking
defaults write com.apple.messageshelper.MessageController SOInputLineSettings -dict-add "continuousSpellCheckingEnabled" -bool false

# Play sound effects
defaults write com.apple.messageshelper.AlertsController PlaySoundsKey -bool false

# Notify me when my name is mentioned
defaults write com.apple.messageshelper.AlertsController SOAlertsAddressMeKey -bool false

# Notify me about messages form unknown contacts
defaults write com.apple.messageshelper.AlertsController NotifyAboutKnockKnockKey -bool false


###############################################################################
# Stats                                                                       #
###############################################################################

# Activate custom config.
defaults write eu.exelban.Stats version -string "2.7.8"

# CPU widget:
# - line chart display
# - display line chart and hide all others
# - show value
# - colorize value
# - colorize based on utilization
defaults write eu.exelban.Stats CPU_widget -string "line_chart"
defaults write eu.exelban.Stats CPU_line_chart_box -bool true
defaults write eu.exelban.Stats CPU_line_chart_frame -bool false
defaults write eu.exelban.Stats CPU_line_chart_value -bool true
defaults write eu.exelban.Stats CPU_line_chart_valueColor -bool true
defaults write eu.exelban.Stats CPU_line_chart_color -string "utilization"

# Deactivate RAM widget.
defaults write eu.exelban.Stats RAM_state -bool false

# Disk widget:
# - hide removable disks
defaults write eu.exelban.Stats Disk_state -bool true
defaults write eu.exelban.Stats Disk_widget -string "memory"
defaults write eu.exelban.Stats Disk_removable -bool false

# Sensors widget:
# - Show first efficiency and performance core temperatures
defaults write eu.exelban.Stats Sensors_state -bool true
defaults write eu.exelban.Stats sensor_Tp01 -bool true
defaults write eu.exelban.Stats sensor_Tp09 -bool true

# Network widget:
# - arrows pictogram
defaults write eu.exelban.Stats Network_speed_icon -string "arrows"

# Battery widget:
# - low level notification at 10%
# - display percentage and time
# - colorize
defaults write eu.exelban.Stats Battery_battery_additional -string "percentageAndTime"
defaults write eu.exelban.Stats Battery_lowLevelNotification -string "0.1"
defaults write eu.exelban.Stats Battery_battery_color -bool true


###############################################################################
# AdGuard                                                                     #
###############################################################################

# Do not block search ads and websites' self-promotion
defaults write com.adguard.mac.adguard UsefulAdsEnabled -bool false

# Activate language-specific filters automaticcaly
defaults write com.adguard.mac.adguard ActivateFiltersAutomaticEnabled -bool true

# Launch AdGuard at Login
defaults write com.adguard.mac.adguard StartAtLogin -bool true

# Hide menu bar icon
defaults write com.adguard.mac.adguard HideMenubarIcon -bool false

# Enable filters
defaults write com.adguard.mac.adguard FilteringEnabled -bool true

# TODO: activate all filters
# Seems to be saved at: ~/Library/Group Containers/XXXXXXXX.com.adguard.mac/Library/Application Support/com.adguard.mac.adguard/adguard.db

# Advanced tracking protection
defaults write com.adguard.mac.adguard StealthEnabled -bool true

# Hide your search queries
defaults write com.adguard.mac.adguard StealthHideSearchQueries -bool true

# Send Do-Not-Track header
defaults write com.adguard.mac.adguard StealthSendDoNotTrackHeader -bool false

# Strip tracking parameters
defaults write com.adguard.mac.adguard StealthStripUrl -bool true

# Self-destruction of third-party cookies after a 10 minutes TTL
defaults write com.adguard.mac.adguard StealthBlockThirdPartyCookiesMin -int 10

# Self-destruction of first-party cookies
defaults write com.adguard.mac.adguard StealthBlockFirstPartyCookies -bool true

# Disable cache for third-party requests
defaults write com.adguard.mac.adguard StealthDisableThirdPartyCache -bool true

# Block third-party Authorization header
defaults write com.adguard.mac.adguard StealthBlockThirdPartyAuthorization -bool true

# Block WebRTC
defaults write com.adguard.mac.adguard StealthBlockWebRtc -bool true

# Block Push API
defaults write com.adguard.mac.adguard StealthBlockBrowserPushApi -bool true

# Block Location API
defaults write com.adguard.mac.adguard StealthBlockBrowserLocationApi -bool true

# Block Java
defaults write com.adguard.mac.adguard StealthBlockBrowserJava -bool true

# Hide Referrer from third-parties
defaults write com.adguard.mac.adguard StealthRemoveReferrerFromThirdPartyRequests -bool true

# Hide your User-Agent
defaults write com.adguard.mac.adguard StealthHideUserAgent -bool true

# Mask your IP address
defaults write com.adguard.mac.adguard StealthHideIp -bool true

# Remove X-Client-Data header
defaults write com.adguard.mac.adguard StealthRemoveXClientDataHeader -bool true

# Phishing and malware protection
defaults write com.adguard.mac.adguard SafebrowsingEnabled -bool true

# Help us with Browsing security filters development
defaults write com.adguard.mac.adguard SafebrowsingHelpEnabled -bool false

# Extensions
defaults write com.adguard.mac.adguard UserscriptsEnabled -bool true

# AdGuard Extra
defaults write com.adguard.mac.adguard ExtraEnabled -bool true

# Automaticcally filter applications
defaults write com.adguard.mac.adguard NetworkFilterEnabled -bool true

# Filter HTTPS protocol
defaults write com.adguard.mac.adguard FilterHttps -bool true

# Do not filter websites with EV certificates
defaults write com.adguard.mac.adguard IgnoreEvSslCertificates -bool false


###############################################################################
# iiNA                                                                        #
###############################################################################

# XXX PlistBuddy seems to overflow with too much commands. Split in two to manage it.
/usr/libexec/PlistBuddy \
    -c "Clear dict" \
    -c "Add :SUAutomaticallyUpdate          integer 1" \
    -c "Add :SUEnableAutomaticChecks        integer 1" \
    -c "Add :SUScheduledCheckInterval       integer 604800" \
    -c "Add :receiveBetaUpdate              integer 0" \
    -c "Add :SUHasLaunchedBefore            integer 1" \
    -c "Add :SUSendProfileInfo              integer 0" \
    -c "Add :enableAdvancedSettings         integer 1" \
    -c "Add :enableLogging                  integer 0" \
    -c "Add :quitWhenNoOpenedWindow         integer 1" \
    -c "Add :keepOpenOnFileEnd              integer 0" \
    -c "Add :resumeLastPosition             integer 0" \
    ~/Library/Preferences/com.colliderli.iina.plist

/usr/libexec/PlistBuddy \
    -c "Add :recordRecentFiles              integer 0" \
    -c "Add :recordPlaybackHistory          integer 0" \
    -c "Add :trackAllFilesInRecentOpenMenu  integer 0" \
    -c "Add :playlistAutoAdd                integer 0" \
    -c "Add :playlistAutoPlayNext           integer 0" \
    -c "Add :screenShotFolder               string  '~/Desktop'" \
    -c "Add :themeMaterial                  integer 4" \
    -c "Add :resizeWindowTiming             integer 0" \
    ~/Library/Preferences/com.colliderli.iina.plist

/usr/libexec/PlistBuddy \
    -c "Add :controlBarToolbarButtons       array" \
    -c "Add :controlBarToolbarButtons:0     integer 2" \
    -c "Add :controlBarToolbarButtons:0     integer 1" \
    -c "Add :controlBarToolbarButtons:0     integer 5" \
    -c "Add :controlBarToolbarButtons:0     integer 0" \
    -c "Add :showChapterPos                 integer 1" \
    -c "Add :autoSearchOnlineSub            integer 1" \
    -c "Add :ytdlSearchPath                 string  ''" \
    ~/Library/Preferences/com.colliderli.iina.plist


###############################################################################
# Transmission.app                                                            #
###############################################################################

# Automatically size window to fit all transfers
defaults write org.m0k.transmission AutoSize -bool true

# Download & Upload Badges
defaults write org.m0k.transmission BadgeDownloadRate -bool false
defaults write org.m0k.transmission BadgeUploadRate -bool false

# Default download location
defaults write org.m0k.transmission DownloadLocationConstant -bool true
defaults write org.m0k.transmission DownloadChoice -string "Constant"
defaults write org.m0k.transmission DownloadFolder -string "${HOME}/Downloads"

# Use `${HOME}/Torrents` to store incomplete downloads
defaults write org.m0k.transmission UseIncompleteDownloadFolder -bool true
defaults write org.m0k.transmission IncompleteDownloadFolder -string "${HOME}/Torrents"

# Use `${HOME}/Downloads` to store completed downloads
defaults write org.m0k.transmission DownloadLocationConstant -bool true

# Don’t prompt for confirmation before downloading
defaults write org.m0k.transmission DownloadAsk -bool false
defaults write org.m0k.transmission MagnetOpenAsk -bool false

# Display window when opening a torrent file
defaults write org.m0k.transmission DownloadAskMulti -bool true
defaults write org.m0k.transmission DownloadAskManual -bool true

# Automatic Import
defaults write org.m0k.transmission AutoImport -bool true
defaults write org.m0k.transmission AutoImportDirectory -string "${HOME}/Downloads/"

# Prompt user for removal of active transfers only when downloading
defaults write org.m0k.transmission CheckRemoveDownloading -bool true

# Do not prompt user for quit, whether there is an active transfer or download.
defaults write org.m0k.transmission CheckQuit -bool false
defaults write org.m0k.transmission CheckQuitDownloading -bool false

# Trash original torrent files
defaults write org.m0k.transmission DeleteOriginalTorrent -bool true

# Hide the donate message
defaults write org.m0k.transmission WarningDonate -bool false
# Hide the legal disclaimer
defaults write org.m0k.transmission WarningLegal -bool false

# Don't play a download sound
defaults write org.m0k.transmission PlayDownloadSound -bool false

# IP block list.
# Source: https://giuliomac.wordpress.com/2014/02/19/best-blocklist-for-transmission/
defaults write org.m0k.transmission BlocklistNew -bool true
defaults write org.m0k.transmission BlocklistURL -string "https://github.com/Naunter/BT_BlockLists/raw/master/bt_blocklists.gz"
defaults write org.m0k.transmission BlocklistAutoUpdate -bool true

# Randomize port on launch
defaults write org.m0k.transmission RandomPort -bool true

# Require encryption
defaults write org.m0k.transmission EncryptionRequire -bool true

# Do not prevent computer from sleeping with active transfer
defaults write org.m0k.transmission SleepPrevent -bool false

# Status bar
defaults write org.m0k.transmission StatusBar -bool true

# Small view
defaults write org.m0k.transmission SmallView -bool true

# Pieces bar
defaults write org.m0k.transmission PiecesBar -bool false

# Pieces bar
defaults write org.m0k.transmission FilterBar -bool true

# Availability
defaults write org.m0k.transmission DisplayProgressBarAvailable -bool false


###############################################################################
# Fork                                                                        #
###############################################################################

# Check stable update every week.
defaults write com.DanPristupov.Fork SUAutomaticallyUpdate -int 1
defaults write com.DanPristupov.Fork applicationUpdateChannel -int 1
defaults write com.DanPristupov.Fork SUScheduledCheckInterval -int 604800

# Default repository source.
defaults write com.DanPristupov.Fork defaultSourceFolder -string "~"

# Set font.
defaults write com.DanPristupov.Fork diffFontName -string "SauceCodeProNerdFontComplete-Regular"
defaults write com.DanPristupov.Fork diffFontSize -int 11

# Disable telemetry.
defaults write com.DanPristupov.Fork disableAnonymousUsageReports -int 1

# Use latest git from brew.
defaults write com.DanPristupov.Fork gitInstanceType -int 3


###############################################################################
# NetNewsWire                                                                 #
###############################################################################

# Check for stable updates.
defaults write com.ranchero.NetNewsWire-Evergreen SUAutomaticallyUpdate -int 1
defaults write com.ranchero.NetNewsWire-Evergreen SUEnableAutomaticChecks -int 1
defaults write com.ranchero.NetNewsWire-Evergreen SUHasLaunchedBefore -int 1

# Refresh every 4 hours.
defaults write com.ranchero.NetNewsWire-Evergreen refreshInterval -int 6

# Hide read feeds and articles.
defaults write com.ranchero.NetNewsWire-Evergreen windowState -dict-add readFeedsFilterState -bool true
defaults write com.ranchero.NetNewsWire-Evergreen windowState -dict-add readArticlesFilterStateValue -bool true


###############################################################################
# Kill affected applications                                                  #
###############################################################################

for app (
    "Activity Monitor"
    "Address Book"
    "Calendar"
    "cfprefsd"
    "Contacts"
    "Dock"
    "Finder"
    "iCal"
    "Mail"
    "Messages"
    "Photos"
    "Safari"
    "SystemUIServer"
    "Transmission"
    # Kill terminal last
    "Terminal"
); do
    killall "${app}" &> /dev/null || true
done
