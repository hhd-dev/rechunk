#!/usr/bin/env bash

if [ $(id -u) -ne 0 ]; then
    echo "Run as superuser"
    exit 1
fi

# run this script outside docker to use your local image cache if 
# applicable, extracts provided image to ./tree
TREE=${TREE:=./tree}
IMAGE_REF=${IMAGE_REF:=ghcr.io/ublue-os/bazzite-deck:40-20240616}

# Dump container image to local dir for modifications
rm -rf $TREE
mkdir -p $TREE
echo Pulling $IMAGE_REF
CREF=$(podman create $IMAGE_REF)
echo Extracting to $TREE
podman export $CREF | tar -C $TREE --same-owner -xf -
podman rm $CREF > /dev/null