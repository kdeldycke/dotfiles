#!/usr/bin/env bash

# Speed-up Grub boot
sudo sed -i 's/GRUB_TIMEOUT=10/GRUB_TIMEOUT=1/g' /etc/default/grub
sudo update-grub

# Scan sensors
#sudo sensors-detect

# Machine-specific config

if [ "$(sudo dmidecode -s system-product-name)" == "MacBookAir5,2" ]; then

# Set CPU governor
sudo tee -a /etc/default/cpufrequtils <<-EOF
# valid values: userspace conservative powersave ondemand performance
# get them from cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors
GOVERNOR="conservative"
EOF

sudo tee -a /etc/sysfs.conf <<-EOF
# by default it's 444, so we have to change permissions to be able to change values
mode devices/system/cpu/cpufreq/conservative = 644
devices/system/cpu/cpufreq/conservative/freq_step = 10
devices/system/cpu/cpufreq/conservative/up_threshold = 45
devices/system/cpu/cpufreq/conservative/ignore_nice_load = 1
devices/system/cpu/cpufreq/conservative/sampling_down_factor = 10
EOF

fi
