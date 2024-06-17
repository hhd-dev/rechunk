#!/usr/bin/env bash
# Prune files in tree that are extraneous
TREE=./tree
TIMESTAMP=1

echo Touching files with timestamp $TIMESTAMP for reproducibility
find $TREE -exec touch -t $TIMESTAMP -m {} +

echo Removing /sysroot and stubbing it
# Main OSTree dir, is not used by consuming scripts, only checked as a sanity check
rm -rf $TREE/sysroot

# Place a stub config file
# TODO: Find if this is needed
mkdir -p $TREE/sysroot/ostree/repo
cat << EOF > $TREE/sysroot/ostree/repo/config
[core]
repo_version=1
mode=bare-split-xattrs
EOF

