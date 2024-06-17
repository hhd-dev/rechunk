#!/usr/bin/env bash
# run this script outside docker to use your local image cache if 
# applicable, extracts provided image to ./tree
TREE=./tree
IMAGE=ghcr.io/ublue-os/bazzite-deck
TAG=40-20240616

# e.g., bazzite-deck
IMAGE_NAME=$(echo $IMAGE | rev | cut -d'/' -f1 | rev)
OUT_TAG=${IMAGE_NAME}_${TAG}

# Dump container image to local dir for modifications
rm -rf $TREE
mkdir -p $TREE
CREF=$(podman create $IMAGE_NAME:$TAG)
podman export $CREF | tar -C $TREE -xf -
podman rm $CREF > /dev/null