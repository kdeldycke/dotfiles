# Kevin's dotfiles

Dot-files and system configuration for Python developers on **macOS** with
Apple Silicon hardware.

![Mac OS X 10.13 High Sierra solarized terminal and vim](https://raw.githubusercontent.com/kdeldycke/dotfiles/main/assets/macos-10.13.jpeg)

## Features

- Aimed at Python programmers using `Neovim` and `VisualStudio Code`.
- Targets `ZSH` shell (now the
  [default since Catalina](https://support.apple.com/en-gb/HT208050)).
- Produce colored output for most of shell commands.
- All color schemes are based on
  [Monokai](https://web.archive.org/web/20161107090516/http://www.monokai.nl/blog/2006/07/).
- Terminal and coding font is
  [Source Code Pro](https://en.wikipedia.org/wiki/Source_Code_Pro).
- Keeps macOS fast, lean and secure.

## Pre-installation

We will reinstall macOS from scratch.

1. Download macOS from the `App Store.app`.

2. Plug a USB drive to your machine, format it with the Disk Utility app,
   double-check it is mounted at `/Volumes/Untitled`, and finally
   [flash it with the macOS image](https://support.apple.com/en-us/HT201372):

   ```shell-session
   $ sudo /Applications/Install\ macOS\ Tahoe.app/Contents/Resources/createinstallmedia --volume /Volumes/Untitled --nointeraction
   ```

3. Reboot your machine, reinstall macOS, create a user.

4. Login to your new user, and launch `System Preferences.app`.

5. Go to `Security & Privacy` → `Privacy` → `Click the lock to make changes`,
   and then unlock with touch ID or password:

   ![](https://raw.githubusercontent.com/kdeldycke/dotfiles/main/assets/system-preferences-security-privacy-unlock.png)

6. Go to `Full Disk Access`, click the `+` button, go to `Applications` →
   `Utilities`, and choose `Terminal.app`:

   ![](https://raw.githubusercontent.com/kdeldycke/dotfiles/main/assets/terminal-full-disk-access.png)

## Install

1. First, you need a local copy of this project.

   If you're lucky and have `git` already installed on your machine, do:

   ```shell-session
   $ cd ~
   $ git clone --recursive https://github.com/kdeldycke/dotfiles.git
   ```

   If you don't have `git` yet, fetch an archive of the repository:

   ```shell-session
   $ mkdir ~/dotfiles
   $ cd ~/dotfiles
   $ curl -fsSL https://github.com/kdeldycke/dotfiles/tarball/main | tar --strip-components 1 -xvzf -
   ```

2. Now you can install the dotfiles on your system:

```shell-session
$ cd ~/dotfiles
$ /bin/zsh ./install.sh 2>&1 | tee ./install.log
```

## Post-installation

Manual setup required to finish up the perfect configuration.

This is a list of manual post-installation steps required to fully configure
the system. Haven't found any way to automate them all.

### `System Preferences.app`

1. In `Displays`, set external monitor scale:

   ![](https://raw.githubusercontent.com/kdeldycke/dotfiles/main/assets/external-display-scale.png)

2. In `Touch ID` → `Add other fingerprints`.

3. In `Security & Privacy` → `Privacy` → `Accessibility`, activate:

   - `Amethyst.app`
   - `Logi Options Daemon`
   - `Logi Options`
   - `MonitorControl.app`

   ![](https://raw.githubusercontent.com/kdeldycke/dotfiles/main/assets/accessibility-preferences.png)

4. In `Security & Privacy` → `Privacy` → `Full Disk Access`, click the `+`
   button. Then go to `Applications` → `Utilities`, to add:

   - `BlockBlock.app`
   - `KnockKnock.app`

5. In `Security & Privacy` → `Privacy` → `Analytics & Improvements`: uncheck
   all options to disallow analytics sharing.

   ![](https://raw.githubusercontent.com/kdeldycke/dotfiles/main/assets/analytics-and-improvements-preferences.png)

6. In `Security & Privacy` → `Privacy` → `Apple Advertising`: uncheck
   `Personalized Ads` option.

   ![](https://raw.githubusercontent.com/kdeldycke/dotfiles/main/assets/apple-advertising-preferences.png)

7. In `Security & Privacy` → `Privacy` → `Developer Tools`, activate
   `Terminal`:

   ![](https://raw.githubusercontent.com/kdeldycke/dotfiles/main/assets/developer-tools-preferences.png)

### SSH

Copy the SSH folder (`./dotfiles/dotfiles/.ssh/`) from Time Machine backups. After restoring, add the public key to GitHub as both an "Authentication key" and a "Signing key" at https://github.com/settings/keys.

### Safari

In `Preferences...` → `Extensions`, activate:

- `AdGuard Assistant`
- `Archive Page`
- `Consent-O-Matic`
- `SimpleLogin`

![](https://raw.githubusercontent.com/kdeldycke/dotfiles/main/assets/safari-active-extensions.png)

### AdGuard

In `Preferences...` → `Filters`, click the `+` button and subscribe to all
filter lists:

![](https://raw.githubusercontent.com/kdeldycke/dotfiles/main/assets/adguard-filter-lists-subscription.png)

### Claude Code

`~/.claude/settings.json` is symlinked to this repo and committed. There is no global `settings.local.json`: `~/.claude/settings.local.json` is [not a supported file](https://github.com/anthropics/claude-code/issues/35703#issuecomment-2818474293).

`enableWeakerNetworkIsolation: true` is set in the sandbox config to work around a macOS sandbox limitation: the sandbox blocks `Security.framework` IPC to `trustd`, breaking TLS certificate verification for all CGO-compiled Go binaries (`gh`, `terraform`, `tofu`, etc.) and Keychain access. `SSL_CERT_FILE` does not help because these binaries use `Security.framework` directly and ignore file-based certs ([anthropics/claude-code#34876](https://github.com/anthropics/claude-code/issues/34876)).

### Logi Options

For productivity, setup custom trackball shortcuts with macOS desktop
management tools and Amethyst windows commands.

Page-up button assignment → `Smart zoom`:

![](https://raw.githubusercontent.com/kdeldycke/dotfiles/main/assets/logitech-mx-ergo-page-up.png)

Page-down button assignment → `Shift` + `Opt` + `Ctrl` + `J`:

![](https://raw.githubusercontent.com/kdeldycke/dotfiles/main/assets/logitech-mx-ergo-page-down.png)

Wheel click button assignment → `Misson Control`:

![](https://raw.githubusercontent.com/kdeldycke/dotfiles/main/assets/logitech-mx-ergo-wheel-click.png)

Wheel left click assignment → `Desktop (left)`:

![](https://raw.githubusercontent.com/kdeldycke/dotfiles/main/assets/logitech-mx-ergo-wheel-left.png)

Wheel right click assignment → `Desktop (right)`:

![](https://raw.githubusercontent.com/kdeldycke/dotfiles/main/assets/logitech-mx-ergo-wheel-right.png)

Side button assignment → `Shift` + `Opt` + `Space`:

![](https://raw.githubusercontent.com/kdeldycke/dotfiles/main/assets/logitech-mx-ergo-side-button.png)

## Upgrade

I'm trying to make the install procedure indempotent so you'll just have to
call the script again to upgrade your system:

```shell-session
$ ./install.sh 2>&1 | tee ./install.log
```

## Maintenance

It mainly consist in refreshing some assets at every macOS major release:

- Regenerate
  [`Monokai Soda.terminal` profile](https://github.com/kdeldycke/dotfiles/blob/main/assets/Monokai%20Soda.terminal).

- Keep list of packages up-to-date:

  ```shell-session
  $ mpm snapshot --update-version ./packages.toml
  ```

- Update screenshots. 😖

## Versions

Only the current default `main` branch is supported and actively maintained.
Older branches are available for archive.

- [macOS 26 (Tahoe)](https://github.com/kdeldycke/dotfiles/tree/main) (current)
- [macOS 15 (Sequoia)](https://github.com/kdeldycke/dotfiles/tree/macos-15)
- [macOS 14 (Sonoma)](https://github.com/kdeldycke/dotfiles/tree/macos-14)
- [macOS 13 (Ventura)](https://github.com/kdeldycke/dotfiles/tree/macos-13)
- [macOS 12 (Monterey)](https://github.com/kdeldycke/dotfiles/tree/macos-12)
- [macOS 11 (Big Sur)](https://github.com/kdeldycke/dotfiles/tree/macos-11)
- [macOS 10.15 (Catalina)](https://github.com/kdeldycke/dotfiles/tree/macos-10.15)
- [macOS 10.14 (Mojave)](https://github.com/kdeldycke/dotfiles/tree/macos-10.14)
- [macOS 10.13 (High Sierra)](https://github.com/kdeldycke/dotfiles/tree/macos-10.13)
- [macOS 10.12 (Sierra)](https://github.com/kdeldycke/dotfiles/tree/macos-10.12)

Former
[support of Kubuntu and Ubuntu Server Linux distributions has been dropped](https://github.com/kdeldycke/dotfiles/commit/e667245f6a4c90c6d41907e392adb74c5acfcf13).
You can still find these as dedicated branches, but all are quite ancient
(2016).

## Resources

- [Awesome macOS command line](https://git.herrbischoff.com/awesome-macos-command-line/about/)
- [`ingrino`'s dotfiles](https://github.com/lingrino/dotfiles)
- [Mathias Bynens `.macos`](https://github.com/mathiasbynens/dotfiles/blob/master/.macos)

## License

For convenience, some third party code and assets are hard-copied in place.
These particular items have their own license and copyright:

- [Monokai Soda](https://github.com/lysyi3m/macos-terminal-themes#monokai-soda-download).

The rest of the content is configuration and code I accumulated over years.
Some was heavily inspired by other dotfiles repositories. But each time I
borrow something, I try to credit the author and/or point to the source. You
should be able to trace back the origin of things by looking at the commit
history.

If you can't find any clue about an external source, then assume it is original
content I produced, which I released under the
[BSD 2-Clause License](LICENSE.md).
