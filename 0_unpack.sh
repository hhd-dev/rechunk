#!/usr/bin/env bash
# run this script outside docker to use your local image cache if 
# applicable, extracts provided image to ./tree

if [ $(id -u) -ne 0 ]; then
    echo "Run as superuser"
    exit 1
fi

if [ -z "$IMAGE_REF" ]; then
    echo "IMAGE_REF is empty"
    exit 1
fi

TREE=${TREE:=./tree}
# Prevent heavy tears by forcing relative path
TREE=./$TREE

# Dump container image to local dir for modifications
rm -rf $TREE
mkdir -p $TREE
echo Pulling $IMAGE_REF
CREF=$(podman create $IMAGE_REF)
echo Extracting to $TREE
podman export $CREF | tar -C $TREE --same-owner -xf -
podman rm $CREF > /dev/null