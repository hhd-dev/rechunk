#!/usr/bin/env bash
# this script creates the ostree from
TREE=./tree
IMAGE=ghcr.io/ublue-os/bazzite-deck
TAG=40-20240616

# e.g., bazzite-deck
IMAGE_NAME=$(echo $IMAGE | rev | cut -d'/' -f1 | rev)
OUT_TAG=${IMAGE_NAME}_${TAG}

# Create a temporary container to pull the
# so we can mount for SELinux
CREF=$(podman create $IMAGE_NAME:$TAG)
MOUNT=$(podman mount $CREF)

# Create a fresh ostree repo
rm -rf ./repo
ostree --repo=./repo init

# Ingest previous tree dir, using mount for SELinux
ostree --repo=./repo commit \
    -b $OUT_TAG \
    --tree=dir=$TREE \
    --consume \
    --bootable \
    --selinux-policy="${MOUNT}"
# --tar-autocreate-parents \ Use this setting if ingesting from tar to avoid error
        
# Cleanup
podman unmount $CREF > /dev/null
podman rm $CREF > /dev/null

echo Created repo with ref "$OUT_TAG"