dotfiles
========

Personal dotfiles, currently designed to work for:

  * **Kubuntu 13.04** (Raring Ringtail)
  * **Mac OSX 10.8** (Mountain Lion)

Snapshots of older distributions may be found as tags of the current repository.


Installation
------------

First, you need a local copy of this project.

If you're lucky and have Git already installed on your machine, do:

    $ cd ~
    $ git clone --recursive https://github.com/kdeldycke/dotfiles.git

If you don't have Git, which is the case on OSX, do:

    $ mkdir ~/dotfiles
    $ cd ~/dotfiles
    $ curl -fsSL https://github.com/kdeldycke/dotfiles/tarball/master | tar --strip-components 1 -xvzf -

Now you can install the dotfiles on your system:

    $ cd ~/dotfiles
    $ ./install.sh


Upgrade
-------

Juste call the installation script again:

    $ ./install.sh


Restore
-------

A backup of the original dotfiles is made when `install.sh` is first called.

To restore the originals, run:

    $ ./install.sh restore

Note that if there was not an original version, the installed links will not be removed.


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

    Solarized - OS X 10.7+ Terminal.App color theme
    Copyright (c) 2013 Tomislav Filipčić
    Distributed under an unknown open-source license
    Source: https://github.com/tomislav/osx-terminal.app-colors-solarized

    Solarized Xresources Color Scheme
    Copyright (c) 2011 Ethan Schoonover
    Distributed under an open-source license
    Source: https://github.com/solarized/xresources
