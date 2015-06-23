dotfiles
========

Collection of dotfiles for Python developers working in vim.

[![Build Status](https://img.shields.io/travis/kdeldycke/maildir-deduplicate/develop.svg?style=flat)](https://travis-ci.org/kdeldycke/dotfiles)

Project is currently targetting:

  * **Kubuntu 14.10** (Utopic Unicorn)
  * **OSX 10.10** (Yosemite)

All running on a [`MacBookAir5,2`](http://www.amazon.com/dp/B008GV6QV2/?tag=kevideld-20).


Features
--------

  * Aimed at Python programmers using vim.
  * Common configuration for both OSX and Kubuntu.
  * Produce colored output for most of shell commands.
  * All color schemes are based on [Solarized](http://ethanschoonover.com/solarized).
  * All Terminal font is [Source Code Pro](https://en.wikipedia.org/wiki/Source_Code_Pro).
  * Keeps OSes fast and lean.


Install
-------

1. First, you need a local copy of this project.

   If you're lucky and have Git already installed on your machine, do:

        $ cd ~
        $ git clone --recursive https://github.com/kdeldycke/dotfiles.git

   If you don't have Git, do:

        $ mkdir ~/dotfiles
        $ cd ~/dotfiles
        $ curl -fsSL https://github.com/kdeldycke/dotfiles/tarball/master | tar --strip-components 1 -xvzf -

2. Now you can install the dotfiles on your system:

        $ cd ~/dotfiles
        $ ./install.sh


Upgrade
-------

I'm trying to make the install procedure indempotent so you'll just have to call the script again to upgrade your system:

    $ ./install.sh


Restore
-------

A backup of the original dotfiles is made when `install.sh` is first called.

To restore the originals, run:

    $ ./install.sh restore

Note that if there was not an original version, the installed links will not be removed.


TODO
----

  * Auto-install Xcode on OSX.
  * Add terminal & vim screenshot on both OSX and Kubuntu.


Old versions
------------

Snapshots of older distributions may be found as tags of the current repository:

  * [Kubuntu 14.04 (Trusty Tahr)](https://github.com/kdeldycke/dotfiles/tree/kubuntu-14.04)
  * [Kubuntu 13.10 (Saucy Salamander)](https://github.com/kdeldycke/dotfiles/tree/kubuntu-13.10)
  * [Kubuntu 13.04 (Raring Ringtail)](https://github.com/kdeldycke/dotfiles/tree/kubuntu-13.04)
  * [OSX 10.9 (Yosemite)](https://github.com/kdeldycke/dotfiles/tree/osx-10.9)
  * [OSX 10.8 (Mountain Lion)](https://github.com/kdeldycke/dotfiles/tree/osx-10.8)


Sources
-------

This repository contain configuration I accumulated over years of daily usage,
but also draws from others:

  * http://kevin.deldycke.com/2006/12/all-my-command-lines/
  * https://github.com/joedicastro/dotfiles/tree/master/vim
  * https://github.com/mathiasbynens/dotfiles
  * https://github.com/sontek/dotfiles
  * https://github.com/reinout/tools

Third party assets:

    Source Code Pro 1.017
    Copyright (c) 2012 Adobe Systems
    Distributed under a SIL Open Font License version 1.1
    Source: https://github.com/adobe-fonts/source-code-pro/releases/latest

    Solarized - OS X 10.7+ Terminal.App color theme
    Copyright (c) 2013 Tomislav Filipčić
    Distributed under an unknown open-source license
    Source: https://github.com/tomislav/osx-terminal.app-colors-solarized

    Solarized - KDE Konsole Settings
    Copyright (c) 2012 Pete Higgins
    Distributed under an unknown open-source license
    Source: https://github.com/phiggins/konsole-colors-solarized

    Solarized Xresources Color Scheme
    Copyright (c) 2011 Ethan Schoonover
    Distributed under an open-source license
    Source: https://github.com/solarized/xresources

    Solarized Color Theme for GNU ls
    Copyright (c) 2013 Sebastian Tramp
    Distributed under a Do What The Fuck You Want To Public License (WTFPL)
    Source: https://github.com/seebi/dircolors-solarized/blob/master/dircolors.256dark
