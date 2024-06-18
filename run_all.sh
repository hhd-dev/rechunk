#!/usr/bin/env bash

if [ $(id -u) -ne 0 ]; then
    echo "Run as superuser"
fi

# Use env file if it exists
if [ -f .env ]; then
    echo "Sourcing .env"
    . .env
fi

if [ -z "$IMAGE_REF" ] || [ -z "$OUT_NAME" ]; then
    echo "IMAGE_REF or OUT_NAME is empty"
    exit 1
fi

# Pin image ref to make sure the SELinux mount
# and extracted ./tree are the same
echo
echo Pulling $IMAGE_REF
export IMAGE_REF=$(podman pull $IMAGE_REF)
export OUT_NAME=${OUT_NAME}

echo
echo Image ref is: $IMAGE_REF
echo "Will save as $OUT_NAME.oci-archive"

echo
echo "##### Unpacking image"
time ./0_unpack.sh
echo
echo "##### Pruning Tree"
time ./1_prune.sh
echo
echo "##### Creating OSTree repo"
time ./2_create.sh

if [[ -z $SKIP_CHUNK ]]; then
    echo
    echo "##### Chunking OSTree repo"
    time ./3_chunk.sh
fi