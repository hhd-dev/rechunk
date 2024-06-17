#!/usr/bin/env bash
# run this script outside docker to use your local image cache if applicable
# extracts provided image to ./tree
IMAGE=ghcr.io/ublue-os/bazzite-deck
TAG=40-20240616

# e.g., bazzite-deck
IMAGE_NAME=$(echo $IMAGE | rev | cut -d'/' -f1 | rev)
OUT_TAG=${IMAGE_NAME}_${TAG}

# Create a temporary container to pull the
# image, and so it can be mounted for SELinux
CREF=$(podman create $IMAGE_NAME:$TAG)
# mount it for SELinux
MOUNT=$(podman mount $CREF)

# Create a fresh ostree repo
rm -rf ./repo
ostree --repo=./repo init

# Feed the container to stdin, and commit it to the repo
# Use the mount for SELinux
podman export $CREF \
    | ostree --repo=./repo commit \
        -b $OUT_TAG \
        --tree=tar=- \
        --bootable \
        --tar-autocreate-parents \
        --selinux-policy="${MOUNT}"
        
# Cleanup
podman unmount $CREF | /dev/null
podman rm $CREF | /dev/null

echo Created repo with ref "$OUT_TAG"