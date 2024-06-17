#!/usr/bin/env bash

if [ $(id -u) -ne 0 ]; then
    echo "Run as superuser"
fi

# Image and tag
IMAGE=${IMAGE:=ghcr.io/ublue-os/bazzite}
TAG=${TAG:=40-20240616}
IMAGE_NAME=$(echo $IMAGE | rev | cut -d'/' -f1 | rev)

# Use this as an intermediary dir for cleanup
TREE=${TREE:=./tree}

# Use this timestamp for reproducibility
TIMESTAMP=${TIMESTAMP:=202001010100}

# # Run podman unshare to enable rootless mounts
# if [ $(id -u) -ne 0 ]; then
#     podman unshare
# fi

echo
echo Pulling ${IMAGE}:${TAG}
IMAGE_REF=$(podman pull ${IMAGE}:${TAG})

echo
echo Image ref is: $IMAGE_REF

OUT_NAME_REF=${IMAGE_NAME}_${TAG}_${IMAGE_REF::5}
OUT_NAME=${OUT_NAME:=$OUT_NAME_REF}
echo "Will save as $OUT_NAME.oci-archive"

echo
echo "##### Unpacking image to $TREE"
time ./0_unpack.sh
echo
echo "##### Pruning $TREE"
time ./1_prune.sh
echo
echo "##### Creating OSTree repo"
time ./2_create.sh

if [[ -z $SKIP_CHUNK ]]; then
    echo
    echo "##### Chunking OSTree repo"
    time ./3_chunk.sh
fi