#!/usr/bin/env bash
set -x

sudo apt update
sudo apt install -y apt-transport-https software-properties-common

sudo add-apt-repository -y ppa:neovim-ppa/stable

sudo apt update
# Force yes so that package maintainer's version of config files always prevail.
sudo apt upgrade -y --force-yes


# Install common packages
for p in $COMMON_SERVER_PACKAGES
do
    sudo apt install -y "$p"
done

# Install Ubuntu specific packages
# Install packages one by one for debug.
#for p in $UBUNTU_SERVER_PACKAGES
#do
#    sudo apt install -y "$p"
#done
sudo apt install -y $UBUNTU_SERVER_PACKAGES


sudo apt install -y python-pip python-dev runsnakerun


sudo apt-file update

sudo deborphan | xargs sudo apt -y remove --purge
sudo apt -y autoremove
