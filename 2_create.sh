#!/usr/bin/env bash

if [ $(id -u) -ne 0 ]; then
    echo "Run as superuser"
    exit 1
fi

# this script creates the ostree from ./tree
# NEEDS TO RUN AS ROOT OR WITH `podman unshare`
TREE=${TREE:=./tree}
IMAGE_REF=${IMAGE_REF:=ghcr.io/ublue-os/bazzite-deck:40-20240616}
OUT_TAG=master

# Create a temporary container to pull the
# so we can mount for SELinux
CREF=$(podman create $IMAGE_REF)
MOUNT=$(podman mount $CREF)

# Create a fresh ostree repo
rm -rf ./repo
ostree --repo=./repo init

# Ingest previous tree dir, using mount for SELinux
ostree --repo=./repo commit \
    -b $OUT_TAG \
    --tree=dir=$TREE \
    --bootable \
    --selinux-policy="${MOUNT}"
# --consume \ # eats the previous dir, makes hard to rerun
# --tar-autocreate-parents \ Use this setting if ingesting from tar to avoid error
        
# Cleanup
podman unmount $CREF > /dev/null
podman rm $CREF > /dev/null

echo Created repo with ref "$OUT_TAG"