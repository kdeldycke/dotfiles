# Kevin's dotfiles

Dot-files and system configuration for Python developers on **macOS**.

![Mac OS X 10.13 High Sierra solarized terminal and vim](https://raw.githubusercontent.com/kdeldycke/dotfiles/main/assets/macos-10.13.jpg)

## Features

* Aimed at Python programmers using `Neovim` and `VisualStudio Code`.
* Targets `Zsh` shell (now the [default since Catalina](https://support.apple.com/en-gb/HT208050)).
* Produce colored output for most of shell commands.
* All color schemes are based on [Monokai](https://web.archive.org/web/20161107090516/http://www.monokai.nl/blog/2006/07/).
* Terminal and coding font is [Source Code Pro](https://en.wikipedia.org/wiki/Source_Code_Pro).
* Keeps macOS fast, lean and secure.

## Pre-installation

We will reinstall macOS from scratch.

1. [Reset NVRAM or PRAM on your Mac](https://support.apple.com/en-us/HT204063).

1. Download macOS from the `App Store.app`.

1. Plug a USB drive to your machine, format it with the Disk Utility app,
double-check it is mounted at `/Volumes/Untitled`, and finally [flash it with
the macOS image](https://support.apple.com/en-us/HT201372):

        ```shell-session
        $ sudo /Applications/Install\ macOS\ Catalina.app/Contents/Resources/createinstallmedia --volume /Volumes/Untitled --nointeraction
        ```

1. Reboot your machine, reinstall macOS, create a user.

1. Login to your new user, and launch `Preferences.app`.

1. Go to `Security & Privacy` > `Privacy` > `Click the lock to make changes.` and then unlock with touch ID or password.

1. Go to `Full Disk Access` > Click the `+` button > Go to `Applications` > `Utilities` > Choose `Terminal.app`.

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
$ ./install.sh 2>&1 | tee ./install.log
```

## Post-installation

Manual setup required to finish up the perfect configuration.

This is a list of manual post-installation steps required to fully configure the system. Haven't found any way to automate them all.

* Go to `Full Disk Access` > Click the `+` button > Go to `Applications` > `Utilities`. Then add:
  * `BlockBlock.app`
  * `KnockKnock.app`
* Copy SSH (`./dotfiles/dotfiles/.ssh/`) and GPG (`./dotfiles/dotfiles/.gnupg/`) keys from backups.
* `System Preferences` -> `Touch ID` -> `Add other fingerprints`.
* Uncheck all options to disallow analytics sharing: `System Preferences` -> `Privacy` -> `Analytics`.
* Check `Limit Ad Tracking` option in: `System Preferences` -> `Privacy` -> `Advertising`.

## Upgrade

I'm trying to make the install procedure indempotent so you'll just have to
call the script again to upgrade your system:

```shell-session
$ ./install.sh 2>&1 | tee ./install.log
```

## Maintenance

### Submodules

To upgrade submodules:

```shell-session
$ git submodule update --recursive --remote
```

## Versions

Only the current default `main` branch is supported and actively maintained. Older
branches are available for archive.

* [macOS 11.0 (BigSur)](https://github.com/kdeldycke/dotfiles/tree/main) (current)
* [macOS 10.15 (Catalina)](https://github.com/kdeldycke/dotfiles/tree/macos-10.15)
* [macOS 10.14 (Mojave)](https://github.com/kdeldycke/dotfiles/tree/macos-10.14)
* [macOS 10.13 (High Sierra)](https://github.com/kdeldycke/dotfiles/tree/macos-10.13)
* [macOS 10.12 (Sierra)](https://github.com/kdeldycke/dotfiles/tree/macos-10.12)
* [Mac OS X 10.11 (El Capitan)](https://github.com/kdeldycke/dotfiles/tree/osx-10.11)
* [Mac OS X 10.10 (Yosemite)](https://github.com/kdeldycke/dotfiles/tree/osx-10.10)
* [Mac OS X 10.9 (Mavericks)](https://github.com/kdeldycke/dotfiles/tree/osx-10.9)
* [Mac OS X 10.8 (Mountain Lion)](https://github.com/kdeldycke/dotfiles/tree/osx-10.8)

Former [support of Kubuntu and Ubuntu Server Linux
distributions has been dropped](https://github.com/kdeldycke/dotfiles/commit/e667245f6a4c90c6d41907e392adb74c5acfcf13). You can still find these as dedicated branches, but all are quite ancient (2016).

## Resources

* [Awesome OSX command line](https://github.com/herrbischoff/awesome-osx-command-line)
* [`ingrino`'s dotfiles](https://github.com/lingrino/dotfiles)
* [Mathias Bynens `.macos`](https://github.com/mathiasbynens/dotfiles/blob/master/.macos)

## License

For convenience, some third party code and assets are hard-copied in place.
These particular items have their own license and copyright:

* [Monokai Soda](https://github.com/lysyi3m/macos-terminal-themes#monokai-soda-download).

The rest of the content is configuration and code I accumulated over years.
Some was heavily inspired by other dotfiles repositories. But each time I
borrow  something, I try to credit the author and/or point to the source. You
should be able to trace back the origin of things by looking at the commit
history.

If you can't find any clue about an external source, then assume it is original
content I produced, which I released under the [BSD 2-Clause License](LICENSE.md).