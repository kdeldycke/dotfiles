# Kevin's dotfiles [![Build Status](https://img.shields.io/travis/kdeldycke/maildir-deduplicate/develop.svg?style=flat)](https://travis-ci.org/kdeldycke/dotfiles)

Dot-files and system configuration for Python developers, currently targetting
**macOS 10.12** (Sierra) and **Kubuntu 16.04 LTS** (Xenial Xerus).

![OSX 10.11 El Capitan solarized terminal and vim
](https://raw.githubusercontent.com/kdeldycke/dotfiles/master/screenshots/osx-10.11.png)

![Kubuntu 15.10 Wily Werewolf solarized terminal and vim
](https://raw.githubusercontent.com/kdeldycke/dotfiles/master/screenshots/kubuntu-15.10.png)


Features
--------

* Aimed at Python programmers using `vim`.
* Common configuration for both macOS and Kubuntu.
* Produce colored output for most of shell commands.
* All color schemes are based on [Solarized
](http://ethanschoonover.com/solarized).
* All terminal font is [Source Code Pro
](https://en.wikipedia.org/wiki/Source_Code_Pro).
* Keeps OSes fast and lean.
* Custom configuration for [`MacBookAir5,2`
](http://www.amazon.com/dp/B008GV6QV2/?tag=kevideld-20) and [`MacBookPro11,1`
](http://www.amazon.com/dp/B0096VBXQE/?tag=kevideld-20).


Install
-------

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


Upgrade
-------

I'm trying to make the install procedure indempotent so you'll just have to
call the script again to upgrade your system:

    $ ./install.sh 2>&1 | tee ./install.log


Restore
-------

A backup of the original dotfiles is made when `install.sh` is first called.

To restore the originals, run:

    $ ./install.sh restore

Note that if there was not an original version, the installed links will not be
removed.


Maintenance
-----------

Once in a while, compare `scripts/osx-config.sh` file with its upstream
template from [Mathias Bynens `.macos`
](https://github.com/mathiasbynens/dotfiles/blob/master/.macos) dotfile:

    $ curl https://raw.githubusercontent.com/mathiasbynens/dotfiles/master/.macos | diff -ru - ./scripts/osx-config.sh

Then merge differences to reduce the differences. This is going to greatly
improve the maintenance of macOS configuration.


Versions
--------

Only the current `master` branch is supported and actively maintained. Older
branches are available for archive.

macOS:

* [macOS 10.12 (Sierra)](https://github.com/kdeldycke/dotfiles/tree/master) (current)
* [OSX 10.11 (El Capitan)](https://github.com/kdeldycke/dotfiles/tree/osx-10.11)
* [OSX 10.10 (Yosemite)](https://github.com/kdeldycke/dotfiles/tree/osx-10.10)
* [OSX 10.9 (Mavericks)](https://github.com/kdeldycke/dotfiles/tree/osx-10.9)
* [OSX 10.8 (Mountain Lion)](https://github.com/kdeldycke/dotfiles/tree/osx-10.8)

Kubuntu:

* [Kubuntu 16.04 LTS (Xenial Xerus)](https://github.com/kdeldycke/dotfiles/tree/master) (current)
* [Kubuntu 15.10 (Wily Werewolf)](https://github.com/kdeldycke/dotfiles/tree/kubuntu-15.10)
* [Kubuntu 15.04 (Vivid Vervet)](https://github.com/kdeldycke/dotfiles/tree/kubuntu-15.04)
* [Kubuntu 14.10 (Utopic Unicorn)](https://github.com/kdeldycke/dotfiles/tree/kubuntu-14.10)
* [Kubuntu 14.04 LTS (Trusty Tahr)](https://github.com/kdeldycke/dotfiles/tree/kubuntu-14.04)
* [Kubuntu 13.10 (Saucy Salamander)](https://github.com/kdeldycke/dotfiles/tree/kubuntu-13.10)
* [Kubuntu 13.04 (Raring Ringtail)](https://github.com/kdeldycke/dotfiles/tree/kubuntu-13.04)


License
-------

For convenience, some third party code and assets are hard-copied in place.
These particular items have their own license and copyright:

* [Source Code Pro](https://github.com/adobe-fonts/source-code-pro/releases/latest) 1.017.
© 2012 Adobe Systems.
SIL Open Font License version 1.1.
* [Solarized for Terminal.App](https://github.com/tomislav/osx-terminal.app-colors-solarized).
© 2013 Tomislav Filipčić.
Unspecified open-source license.
* [Solarized for Konsole](https://github.com/phiggins/konsole-colors-solarized).
© 2012 Pete Higgins.
Unspecified open-source license.
* [Solarized for Xresources](https://github.com/solarized/xresources).
© 2011 Ethan Schoonover.
Unspecified open-source license.
* [Solarized for GNU ls](https://github.com/seebi/dircolors-solarized/blob/master/dircolors.256dark).
© 2013 Sebastian Tramp.
Do What The Fuck You Want To Public License (WTFPL).
* [Python shell enhancement](https://github.com/jbisbee/python-shell-enhancement).
© 2013 Jeff Bisbee.
MIT license.

The rest of the content is configuration and code I accumulated over years.
Some was heavily inspired by other dotfiles repositories. But each time I
borrow  something, I try to credit the author and/or point to the source. You
should be able to trace back the origin of things by looking at the commit
history.

If you can't find any clue about an external source, then assume it is original
content I produced, which I released under the [BSD 2-Clause License
](LICENSE.md).
