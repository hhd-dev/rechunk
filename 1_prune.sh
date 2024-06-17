#!/usr/bin/env bash

if [ $(id -u) -ne 0 ]; then
    echo "Run as superuser"
    exit 1
fi

# Prune files in tree that are extraneous
TREE=${TREE:=./tree}
TIMESTAMP=${TIMESTAMP:=202001010100}

# Main OSTree dir, is not used by consuming scripts, only checked as a sanity check
echo Pruning files in $TREE
rm -rf $TREE/sysroot
rm -r $TREE/ostree

# Remove duplicate files
# rm -rf $TREE/etc/containers/policy.json
# rm -rf $TREE/etc/yafti.yml

# Touch files for reproducibility
# TODO: Check / may not be needed
echo Touching files with timestamp $TIMESTAMP for reproducibility
sudo find $TREE -exec touch -t $TIMESTAMP -h {} + &> /dev/null
