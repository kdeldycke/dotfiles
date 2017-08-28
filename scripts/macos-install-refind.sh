#!/usr/bin/env bash
set -x

# Search for a Linux partition.
sudo fdisk -d /dev/disk0 | cut -d ',' -f 3 | grep --quiet "0x83"

if [[ $? -ne 0 ]]; then

    echo "No Linux partition found. Skip rEFInd install."

else

    echo "Linux partition found. Try to install rEFInd."

    # Check if SIP is going to let us mess with boot process.
    csrutil status | grep --quiet "disabled"

    if [[ $? -ne 0 ]]; then

        echo "System Integrity Protection is enabled. Can't install rEFInd."
        echo "See: http://mattjanik.ca/blog/2015/10/01/refind-on-el-capitan/"

    else

        REFIND_VERSION="0.11.0"

        # Download refind.
        wget https://netcologne.dl.sourceforge.net/project/refind/$REFIND_VERSION/refind-bin-$REFIND_VERSION.zip -O "$TMPDIR/refind-bin-$REFIND_VERSION.zip"
        unzip "$TMPDIR/refind-bin-$REFIND_VERSION.zip" -d "$TMPDIR"

        # Remove previous installation.
        sudo $TMPDIR/refind-bin-$REFIND_VERSION/mountesp
        sudo rm -rf /Volumes/esp/EFI/refind
        sudo rm -rf /Volumes/esp/EFI/BOOT

        # Install custom bootloader.
        $TMPDIR/refind-bin-$REFIND_VERSION/refind-install --yes

        # Adjust personnal refind config.
        sudo $TMPDIR/refind-bin-$REFIND_VERSION/mountesp
        sudo sed -i "s/timeout 20/timeout 1/" /Volumes/esp/EFI/refind/refind.conf
        # See: http://www.rodsbooks.com/refind/configfile.html#default
        # sudo sed -i "s/#default_selection 1/default_selection linux/" /Volumes/esp/EFI/refind/refind.conf

        # Cleanup.
        rm -rf $TMPDIR/refind-bin-$REFIND_VERSION*

    fi

fi
