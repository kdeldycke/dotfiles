#!/usr/bin/env bash
set -x

# Check if SIP is going to let us mess with boot process.
csrutil status | grep --quiet "disabled"

if [[ $? -ne 0 ]]; then

    echo "System Integrity Protection is enabled. Can't install rEFInd."
    echo "See: http://mattjanik.ca/blog/2015/10/01/refind-on-el-capitan/"

else

    REFIND_VERSION="0.10.3"

    # Download refind.
    curl -O http://netcologne.dl.sourceforge.net/project/refind/$REFIND_VERSION/refind-bin-$REFIND_VERSION.zip
    unzip ./refind-bin-$REFIND_VERSION.zip

    # Remove previous installation.
    sudo ./refind-bin-$REFIND_VERSION/mountesp
    sudo rm -rf /Volumes/esp/EFI/refind
    sudo rm -rf /Volumes/esp/EFI/BOOT

    # Install custom bootloader.
    ./refind-bin-$REFIND_VERSION/refind-install

    # Adjust personnal refind config.
    sudo ./refind-bin-$REFIND_VERSION/mountesp
    sudo sed -i "s/timeout 20/timeout 1/" /Volumes/esp/EFI/refind/refind.conf
    sudo sed -i "s/#default_selection 1/default_selection linux/" /Volumes/esp/EFI/refind/refind.conf

    # Cleanup.
    rm -rf ./refind-bin-$REFIND_VERSION*

fi
