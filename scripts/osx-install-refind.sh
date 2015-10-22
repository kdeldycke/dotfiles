#!/usr/bin/env bash -x

# Check if SIP is going to let us mess with boot process.
csrutil status | grep --quiet "disabled"

if [[ $? -ne 0 ]]; then

    echo "System Integrity Protection is enabled. Can't install rEFInd."
    echo "See: http://mattjanik.ca/blog/2015/10/01/refind-on-el-capitan/"

else

    # Remove previous install of refind bootloader first.
    mkdir /Volumes/esp
    sudo mount -t msdos /dev/disk0s1 /Volumes/esp
    sudo rm -rf /Volumes/esp/EFI/refind
    sudo rm -rf /Volumes/esp/EFI/BOOT
    sudo diskutil umount /Volumes/esp

    # Install custom bootloader.
    curl -O http://freefr.dl.sourceforge.net/project/refind/0.9.2/refind-bin-0.9.2.zip
    unzip ./refind-bin-0.9.2.zip
    ./refind-bin-0.9.2/install.sh --alldrivers
    rm -rf ./refind-bin-0.9.2*
    sudo diskutil umount /Volumes/esp

    # Fix Yosemite boot. Source: http://www.rodsbooks.com/refind/yosemite.html
    mkdir /Volumes/esp
    sudo mount -t msdos /dev/disk0s1 /Volumes/esp

    # Adjust personnal refind config
    sudo sed -i "" -e "s/timeout 20/timeout 1/" /Volumes/esp/EFI/refind/refind.conf
    sudo sed -i "" -e "s/#default_selection 1/default_selection linux/" /Volumes/esp/EFI/refind/refind.conf

fi
