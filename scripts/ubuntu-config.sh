#!/usr/bin/env bash

# Speed-up Grub boot
sudo sed -i 's/GRUB_TIMEOUT=10/GRUB_TIMEOUT=1/g' /etc/default/grub
sudo update-grub


# It is highly recommended to use the fan controller daemon that is included in the mactel-support ppa called macfanctl.
# Source: http://download.maketecheasier.com/mba52/post-install-quantal.sh
# sudo add-apt-repository ppa:mactel-support/ppa
# sudo aptitude update
# sudo aptitude install -y macfanctld
# sudo service macfanctld stop
# sudo sed -i "s/\(^exclude:\).*\$/\\1 16 17 20/" /etc/macfanctl.conf
# sudo service macfanctld start

# sudo tee -a /etc/modprobe.d/hid_apple.conf <<-EOF
#   options hid_apple fnmode=2
# EOF
# sudo modprobe hid_apple

# wget -Nq http://pof.eslack.org/archives/files/mba42/00_usercustom || wget -Nq http://almostsure.com/mba42/00_usercustom
# sed -i "s/xxxxxxxx/$USER/" 00_usercustom
# chmod 0755 00_usercustom
# sudo mv 00_usercustom /etc/pm/sleep.d/00_usercustom
#
# wget -Nq http://pof.eslack.org/archives/files/mba42/dotXmodmap || wget -Nq http://www.almostsure.com/mba42/dotXmodmap
# mv dotXmodmap ~/.Xmodmap
# xmodmap ~/.Xmodmap

# TODO: test
# wget -Nq http://pof.eslack.org/archives/files/mba42/99_macbookair || wget -Nq http://www.almostsure.com/mba42/99_macbookair
# chmod 0755 99_macbookair
# sudo mv 99_macbookair /etc/pm/power.d/99_macbookair

# # --- re-enable hibernate
# # https://help.ubuntu.com/12.04/ubuntu-help/power-hibernate.html
# sudo tee /etc/polkit-1/localauthority/50-local.d/com.ubuntu.enable-hibernate.pkla <<-EOF
# [Re-enable hibernate by default]
# Identity=unix-user:*
# Action=org.freedesktop.upower.hibernate
# ResultActive=yes
# EOF
# gsettings set org.gnome.settings-daemon.plugins.power critical-battery-action 'hibernate'
