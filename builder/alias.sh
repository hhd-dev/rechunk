#!/usr/bin/env bash

# Use host
# CONTAINER_CACHE=/var/cache/containers
# Or just a normal volume
CONTAINER_CACHE=${CONTAINER_CACHE:=container_cache}

alias fd="sudo podman run\
    -it --rm -v \$(pwd):/workspace -w /workspace \
    -v $CONTAINER_CACHE:/var/lib/containers \
    --privileged --device /dev/fuse --security-opt label:disable \
    -u \$(id -u):\$(id -g) \
    fedora_build"