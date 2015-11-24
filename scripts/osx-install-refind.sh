#!/usr/bin/env bash
set -x

# Check if SIP is going to let us mess with boot process.
csrutil status | grep --quiet "disabled"

if [[ $? -ne 0 ]]; then

    echo "System Integrity Protection is enabled. Can't install rEFInd."
    echo "See: http://mattjanik.ca/blog/2015/10/01/refind-on-el-capitan/"

else

    # Download refind.
    curl -O http://netcologne.dl.sourceforge.net/project/refind/0.10.0/refind-bin-0.10.0.zip
    unzip ./refind-bin-0.10.0.zip

    # Remove previous installation.
    ./refind-bin-0.10.0/mountesp
    sudo rm -rf /Volumes/esp/EFI/refind
    sudo rm -rf /Volumes/esp/EFI/BOOT

    # Install custom bootloader.
    ./refind-bin-0.10.0/refind-install --alldrivers

    # Adjust personnal refind config.
    sudo sed -i "" -e "s/timeout 20/timeout 1/" /Volumes/esp/EFI/refind/refind.conf
    sudo sed -i "" -e "s/#default_selection 1/default_selection linux/" /Volumes/esp/EFI/refind/refind.conf

    # Cleanup.
    rm -rf ./refind-bin-0.10.0*

fi
