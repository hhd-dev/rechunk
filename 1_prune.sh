#!/usr/bin/env bash
# Prune files in tree that are extraneous
TREE=./tree
TIMESTAMP=1

echo Touching files with timestamp $TIMESTAMP for reproducibility
find $TREE -exec touch -t $TIMESTAMP -m {} +

# Main OSTree dir, is not used by consuming scripts, only checked as a sanity check
rm -rf $TREE/sysroot