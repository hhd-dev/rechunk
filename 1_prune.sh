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
rm -rf $TREE/ostree

# Remove extra etc dir, not needed
# Causes errors with both loading on podman and
# when deploying
rm -rf $TREE/etc
# ln -s usr/etc $TREE/etc # TODO: Check it works for container UX

# Remove duplicate files
# rm -rf $TREE/etc/containers/policy.json
# rm -rf $TREE/etc/yafti.yml

# Touch files for reproducibility
# TODO: Check / may not be needed
echo Touching files with timestamp $TIMESTAMP for reproducibility
sudo find $TREE -exec touch -t $TIMESTAMP -h {} + &> /dev/null
