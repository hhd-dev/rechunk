#!/usr/bin/env bash

if [ $(id -u) -ne 0 ]; then
    echo "Run as superuser"
    exit 1
fi

# this script creates the ostree from ./tree
TREE=${TREE:=./tree}
REPO=${REPO:=./repo}
OUT_TAG=${OUT_TAG:=master}

# # Due to using a buildah mount this is not required
# # Create a temporary container to pull the
# # so we can mount for SELinux

# Create an ostree repo
if [ -n "$INIT_REPO" ] | [ ! -d "$REPO" ]; then
    echo
    echo "Initializing OSTree repo"
    rm -rf $REPO
    ostree --repo=$REPO init --mode=bare-user
    # Set option to reduce fsync for transient builds
    ostree --repo=$REPO config set 'core.fsync' 'false'
fi

echo
echo Creating repo with ref "$OUT_TAG"
# Ingest previous tree dir
ostree --repo=$REPO commit \
    -b $OUT_TAG \
    --tree=dir=$TREE \
    --bootable \
    --selinux-policy=$TREE \
    --selinux-labeling-epoch=1
        
echo Commited ref "$OUT_TAG" to repo "$REPO"