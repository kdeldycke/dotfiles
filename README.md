dotfiles
========

Personal dotfiles, currently designed to work for:

  * **Kubuntu 13.04**
  * **Mac OSX 10.8 (Mountain Lion)**

Snapshots of older distributions may be found as tags of the current repository.


Ubuntu install
--------------

Run:

    $ cd
    $ git clone --recursive https://github.com/kdeldycke/dotfiles.git
    $ cd dotfiles
    $ ./ubuntu-install.sh


OSX install
-----------

Run:

    $ cd
    $ git clone --recursive https://github.com/kdeldycke/dotfiles.git
    $ cd dotfiles
    $ ./osx-install.sh


Restore previous dotfiles
-------------------------

A backup of the original dotfiles is made when `./[ubuntu|osx]-install.sh` is first called.

To restore the originals, run:

    $ ./common.sh restore

Note that if there was not an original version, the installed links will not be removed.


TODO
----

  * Update install instructions: there is no git on a pristine OSX.


Sources
-------

This repository contain configuration I accumulated over years of daily usage,
but also draws from others:

  * http://kevin.deldycke.com/2006/12/all-my-command-lines/
  * https://github.com/mathiasbynens/dotfiles
  * https://github.com/sontek/dotfiles
  * https://github.com/reinout/tools
