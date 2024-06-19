#!/usr/bin/env bash

if [ $(id -u) -ne 0 ]; then
    echo "Run as superuser"
    exit 1
fi
set -e

# Use env file if it exists
if [ -f .env ]; then
    echo "Sourcing .env"
    . .env
fi

if [ -z "$IMAGE_REF" ] || [ -z "$OUT_NAME" ]; then
    echo "IMAGE_REF or OUT_NAME is empty"
    exit 1
fi

# Load and mount image to ./tree
echo
echo Creating a $IMAGE_REF container
export CREF=$(buildah from $IMAGE_REF)
export OUT_NAME=${OUT_NAME}
export TREE=${TREE:=./tree}

# Prevent heavy tears by forcing relative path
TREE=./$TREE
rm -rf $TREE
MOUNT=$(buildah mount $CREF)
ln -s $MOUNT $TREE

echo
echo Image ref is: $IMAGE_REF

echo "##### Pruning Tree"
time ./1_prune.sh

# Now that the destructive actions are done
# switch to absolute path
# Required by OSTree
TREE=$MOUNT

echo
echo "##### Creating OSTree repo"
time ./2_create.sh

# Cleanup
echo
echo "##### Removing interim container"
buildah unmount $CREF > /dev/null
buildah rm $CREF > /dev/null

if [[ -z $SKIP_CHUNK ]]; then
    echo
    echo "##### Chunking OSTree repo"
    time ./3_chunk.sh
fi