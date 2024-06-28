#!/usr/bin/env bash

# Use host
# CONTAINER_CACHE=/var/cache/containers
# Or just a normal volume
VOL_CONTAINER_CACHE=${VOL_CONTAINER_CACHE:=container_cache}
VOL_OSTREE_CACHE=${VOL_OSTREE_CACHE:=ostree_cache}

alias fd="sudo podman run -it --rm \
    -v \$(pwd):/workspace -w /workspace \
    -v '$VOL_CONTAINER_CACHE':/var/lib/containers \
    -v '$VOL_OSTREE_CACHE':/var/ostree/repo \
    -v \${TREE:=\$(pwd)/tree}:/var/tree \
    -e REPO=/var/ostree \
    --privileged --device /dev/fuse --security-opt label:disable \
    -u \$(id -u):\$(id -g) \
    fedora_build"
    # -e TREE=/var/tree \

oci_extract() {
    # Extract an oci image
    if [[ -z $1 ]]; then
        echo "Missing argument. Usage: oci_extract <oci-dir>"
        exit 1
    fi
    cname=$1
    echo "Removing old extracted files"
    sudo rm -rf $cname/extracted 
    
    i=0
    for l in $(sudo skopeo inspect oci:$1 | jq -c '.LayersData[] | select(.MIMEType | contains("tar+gzip"))'); do
        out_name=$(echo $l | jq -r '.Annotations."ostree.components"' | cut -c1-20)
        out_name=${out_name:-noname}
        out_name=$(printf "%20s" "$out_name" | tr ' ' '_')
        hash=$(echo $l | jq -r '.Digest' | cut -d'.' -f1)
        echo "Extracting layer $out_name with $hash"
        sudo mkdir -p $cname/extracted/$out_name
        sudo tar -xzf $cname/blobs/sha256/$(echo $hash | cut -d':' -f 2) -C $cname/extracted/$out_name
    done
}

oci_analyze() {
    # Analyze an oci image
    if [[ -z $1 ]]; then
        echo "Missing argument. Usage: oci_analyze <oci-dir>"
        exit 1
    fi
    cname=$1
    
    i=0
    for info in $(sudo skopeo inspect oci:$1 | jq -c '.LayersData[] | select(.MIMEType | contains("tar+gzip"))'); do
        hash=$(echo $i | cut -d'.' -f1)
        layer_name=$(printf "%05d\n" $i)
        layer_dir=$cname/extracted/$layer_name
        
        echo
        echo "######## Layer ${layer_name}: $(echo $info | jq -r '.Digest' | cut -d':' -f 2 | cut -c1-15)"
        echo Packages: $(echo "$info" | jq -r '.Annotations."ostree.components"')
        echo Compressed Size: $(echo "$info" | jq -r '.Size' | numfmt --to=iec)

        echo
        echo Top Level Directories:
        sudo bash -c "cd $layer_dir && du -h --max-depth 3 -P --threshold=10M --exclude=sysroot . | sort -r -h"
        i=$(( i + 1 ))
    
        echo
        echo "Top files (> 10MB):"
        sudo bash -c "cd $layer_dir && find . -type f -exec du -a -h --threshold=10M {} + | grep -v 'sysroot' | sort -r -h | tail -n 50"
    done
}

oci_compare() {
    # Compare 2 oci images
    if [[ -z $1 || -z $2 ]]; then
        echo "Missing arguments. Usage: oci_compare <prev> <next>"
        exit 1
    fi

    layers=()
    for i in $1 $2; do
        layers+=$(sudo skopeo inspect oci:$i | jq -r '.LayersData[] | select(.MIMEType | contains("tar+gzip")) | .Digest');
    done

    diff <(echo $layers[1]) <(echo $layers[2])
}

oci_diff() {
    # Compare 2 oci images
    if [[ -z $1 || -z $2 ]]; then
        echo "Missing arguments. Usage: oci_compare <prev> <next>"
        exit 1
    fi

    sudo rsync --stats -n -i -rlHAX --links \
        --no-t --delete --exclude sysroot \
        $2/extracted/ $1/extracted/ | grep -v ">f..T......"
}

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

compa() {
    # compare 2 file attributes
    # 1 and 2 are mounted instances of the diffedd and original image
    for i in $1/$3 $2/$3; do
        echo "######## $i"
        sudo stat -c "%a" $i
        sudo getfattr -h -d -m '' $i
    done
}