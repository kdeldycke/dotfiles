# Kevin's dotfiles

Dot-files and system configuration for Python developers on **macOS**.

![Mac OS X 10.13 High Sierra solarized terminal and vim](https://raw.githubusercontent.com/kdeldycke/dotfiles/master/screenshots/macos-10.13.jpg)


## Features

* Aimed at Python programmers using `Neovim`.
* Produce colored output for most of shell commands.
* All color schemes are based on [Solarized](http://ethanschoonover.com/solarized).
* Terminal and coding font is [Source Code Pro](https://en.wikipedia.org/wiki/Source_Code_Pro).
* Keeps macOS fast, lean and secure.


## Pre-installation

1. [Reset NVRAM or PRAM on your Mac](https://support.apple.com/en-us/HT204063).

1. Download macOS from the App Store.

1. Plug a USB drive to your machine, format it with the Disk Utility app,
double-check it is mounted at `/Volumes/Untitled`, and finally [flash it with
the macOS image](https://support.apple.com/en-us/HT201372):

    $ sudo /Applications/Install\ macOS\ Mojave.app/Contents/Resources/createinstallmedia --volume /Volumes/Untitled --nointeraction


## Install

1. First, you need a local copy of this project.

   If you're lucky and have `git` already installed on your machine, do:

        $ cd ~
        $ git clone --recursive https://github.com/kdeldycke/dotfiles.git

   If you don't have `git` yet, fetch an archive of the repository:

        $ mkdir ~/dotfiles
        $ cd ~/dotfiles
        $ curl -fsSL https://github.com/kdeldycke/dotfiles/tarball/master | tar --strip-components 1 -xvzf -

2. Now you can install the dotfiles on your system:

        $ cd ~/dotfiles
        $ ./install.sh 2>&1 | tee ./install.log


## Post-installation

Manual setup required to finish up the perfect configuration.

This is a list of manual post-installation steps required to fully configure the system. Haven't found any way to automate them all.

* Copy SSH (`./dotfiles/dotfiles/.ssh/`) and GPG (`./dotfiles/dotfiles/.gnupg/`) keys from backups.
* `System Preferences` -> `Touch ID` -> `Add other fingerprints`.
* Give `/Applications/Utilities/Terminal.app` full disk access: `System Preferences` -> `Privacy` -> `Full Disk Access`.
* Give `/Applications/Utilities/Dropbox.app` accessibility permissions: `System Preferences` -> `Privacy` -> `Accessibility`.
* Uncheck all options to disallow analytics sharing: `System Preferences` -> `Privacy` -> `Analytics`.
* Check `Limit Ad Tracking` option in: `System Preferences` -> `Privacy` -> `Advertising`.


## Upgrade

I'm trying to make the install procedure indempotent so you'll just have to
call the script again to upgrade your system:

    $ ./install.sh 2>&1 | tee ./install.log


## Maintenance

Once in a while, compare `scripts/macos-config.sh` file with its upstream
template from [Mathias Bynens `.macos`](https://github.com/mathiasbynens/dotfiles/blob/master/.macos) dotfile:

    $ curl https://raw.githubusercontent.com/mathiasbynens/dotfiles/master/.macos | diff -ru - ./scripts/macos-config.sh

Then merge differences to reduce the differences. This is going to greatly
improve the maintenance of macOS configuration.


## Versions

Only the current `master` branch is supported and actively maintained. Older
branches are available for archive.

* [macOS 10.15 (Catalina)](https://github.com/kdeldycke/dotfiles/tree/master) (current)
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


## License

For convenience, some third party code and assets are hard-copied in place.
These particular items have their own license and copyright:

* [Source Code Pro](https://github.com/adobe-fonts/source-code-pro/releases/latest) 2.030.
© 2016 Adobe Systems.
SIL Open Font License version 1.1.
* [Solarized for Terminal.App](https://github.com/tomislav/osx-terminal.app-colors-solarized).
© 2013 Tomislav Filipčić.
Unspecified open-source license.

The rest of the content is configuration and code I accumulated over years.
Some was heavily inspired by other dotfiles repositories. But each time I
borrow  something, I try to credit the author and/or point to the source. You
should be able to trace back the origin of things by looking at the commit
history.

If you can't find any clue about an external source, then assume it is original
content I produced, which I released under the [BSD 2-Clause License](LICENSE.md).
