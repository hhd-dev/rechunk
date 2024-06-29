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

# Volumes
VOL_CONTAINER_CACHE=${VOL_CONTAINER_CACHE:=container_cache}
VOL_OSTREE_CACHE=${VOL_OSTREE_CACHE:=ostree_cache}

# Load and mount image to ./tree
echo
echo Creating a $IMAGE_REF container
export CREF=$(podman create $IMAGE_REF)
export OUT_NAME
export OUT_TAG
export PREV_NAME
export MAX_LAYERS
export PREFILL_RATIO

# Prevent heavy tears by forcing relative path
MOUNT=$(podman mount $CREF)
if [ -z $MOUNT ] ; then
    echo "Mount is empty."
    exit 1
fi
export TREE=${MOUNT}
echo "Mounted at '$MOUNT'"

if [ -n "$JUST_MOUNT" ]; then
    echo "Skipping other steps due to JUST_MOUNT."
    exit 0
fi

echo
echo Image ref is: $IMAGE_REF

echo "##### Pruning Tree"
podman run -it --rm \
    -v $(pwd):/workspace -w /workspace \
    -v "$VOL_CONTAINER_CACHE":/var/lib/containers \
    -v "$TREE":/var/tree \
    -e TREE=/var/tree \
    -u 0:0 \
    fedora_build \
    bash -c "time ./1_prune.sh"

if [ -n "$JUST_PRUNE" ]; then
    echo "Skipping other steps due to JUST_PRUNE."
    echo "Mounted at '$MOUNT'"
    echo "Symlink to '$TREE'"
    exit 0
fi
# Now that the destructive actions are done
# switch to absolute path
# Required by OSTree
TREE=$MOUNT

echo
echo "##### Creating OSTree repo"
podman run -it --rm \
    -v $(pwd):/workspace -w /workspace \
    -v "$VOL_CONTAINER_CACHE":/var/lib/containers \
    -v "$VOL_OSTREE_CACHE":/var/ostree \
    -e REPO=/var/ostree/repo \
    -v "$TREE":/var/tree \
    -e TREE=/var/tree \
    -e OUT_TAG \
    -u 0:0 \
    fedora_build \
    bash -c "time ./2_create.sh"

# Cleanup
echo
echo "##### Removing interim container"
podman unmount $CREF > /dev/null
podman rm $CREF > /dev/null

if [[ -n $JUST_COMMIT ]]; then
    echo "Skipping chunking due to JUST_COMMIT."
    exit 0
fi

echo
echo "##### Chunking OSTree repo"
time ./3_chunk.sh