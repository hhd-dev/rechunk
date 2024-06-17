#!/usr/bin/env bash
# run this script outside docker to use your local image cache if 
# applicable, extracts provided image to ./tree
TREE=${TREE:=./tree}
IMAGE_REF=${IMAGE_REF:=ghcr.io/ublue-os/bazzite-deck:40-20240616}

# Dump container image to local dir for modifications
rm -rf $TREE
mkdir -p $TREE
CREF=$(podman create $IMAGE_REF)
podman export $CREF | tar -C $TREE -xf -
podman rm $CREF > /dev/null