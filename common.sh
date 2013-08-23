#!/usr/bin/env bash

# Ask for the administrator password upfront
sudo -v

# We need to distinguish sources and binary packages for Brew & Cask on OSX
COMMON_PACKAGES="git vim jnettop hfsutils unrar subversion colordiff faac flac lame x264 inkscape graphviz qemu lftp shntool testdisk fdupes recode pngcrush exiftool rtmpdump optipng colortail colorsvn mercurial"
BIN_PACKAGES="audacity avidemux dropbox firefox gimp inkscape vlc blender thunderbird virtualbox bitcoin-qt wireshark"

# Define global Python packages
PYTHON_PACKAGES="readline pip setuptools virtualenv distribute pep8 pyflakes"

# Sync dot files
rsync --exclude ".git/" --exclude ".DS_Store" --exclude ".gitignore" --exclude ".gitmodules" --exclude "*.sh" --exclude "*.swp" --exclude "*.md" -av --no-perms . ~
