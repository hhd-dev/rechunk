#!/usr/bin/env bash
# Prune files in tree that are extraneous
TREE=${TREE:=./tree}
TIMESTAMP=${TIMESTAMP:=202001010100}

# Main OSTree dir, is not used by consuming scripts, only checked as a sanity check
echo Pruning files in $TREE
rm -rf $TREE/sysroot

# Touch files for reproducibility
echo Touching files with timestamp $TIMESTAMP for reproducibility
sudo find $TREE -exec touch -t $TIMESTAMP -m {} + &> /dev/null
