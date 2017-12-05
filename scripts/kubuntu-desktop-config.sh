#!/usr/bin/env bash
set -x

# Speed-up Grub boot, but always show the boot menu.
sudo sed -i 's/GRUB_TIMEOUT=10/GRUB_TIMEOUT=1/g' /etc/default/grub
sudo sed -i 's/GRUB_HIDDEN_TIMEOUT/#GRUB_HIDDEN_TIMEOUT/g' /etc/default/grub
sudo update-grub

# Scan sensors
#sudo sensors-detect
