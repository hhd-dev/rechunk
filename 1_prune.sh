#!/usr/bin/env bash
# Prune files in tree that are extraneous

if [ $(id -u) -ne 0 ]; then
    echo "Run as superuser"
    exit 1
fi

TREE=${TREE:=./tree}
TIMESTAMP=${TIMESTAMP:=202001010100}

# Prevent heavy tears by forcing relative path
TREE=./$TREE

# Main OSTree dir, is remade in the end
# If it contains kinoite files that were removed by bazzite,
# they will be retained, bloating the final image
echo Pruning files in $TREE
rm -rf $TREE/sysroot
rm -rf $TREE/ostree

# Merge /usr/etc to /etc
# OSTree will error out if both dirs exist
# And rpm-ostree will be confused and use only one of them
cp -r --preserve=links --remove-destination \
    $TREE/etc/* $TREE/usr/etc/
rm -r $TREE/etc

# Make basic dirs
# that OSTree expects and will panic without
# (initramfs script will fail)
# https://github.com/M1cha/archlinux-ostree/

mkdir -p $TREE/sysroot
ln -s sysroot/ostree $TREE/ostree

# Deal with /boot?

# Touch files for reproducibility
# TODO: Check / may not be needed
echo Touching files with timestamp $TIMESTAMP for reproducibility
sudo find $TREE -exec touch -t $TIMESTAMP -h {} + &> /dev/null
