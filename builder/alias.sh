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

compl() {
    # Compare 2 layer's contents
    if [[ -z $1 || -z $2 ]]; then
        echo "Missing arguments. Usage: compare <oci1>:<hash1> <oci2>:<hash2>"
        exit 1
    fi
    mkdir -p comp
    rm -rf comp/$1 comp/$2

    outd=()
    for i in $1 $2; do
        cname=$(echo $i | cut -d':' -f1)
        hash=$(echo $i | cut -d':' -f2)
        out=comp/${cname}_${hash:0:4}
        mkdir -p $out
        outd+=($out)
        tar -xzf $cname/blobs/sha256/$hash -C $out
    done

    sudo diff --brief --recursive --no-dereference $outd | grep -v "sysroot/ostree"
}