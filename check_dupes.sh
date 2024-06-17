#!/usr/bin/env bash

# If the tars contain duplicate files,
# podman will fail to load them so the
# OCI can not be uploaded.

# Point to an extracted oci-archive dir
# This script will print duplicate entries
# in the tar files

# Check OCI var is set and if not exit
if [ -z $OCI ]; then
  echo "OCI variable not set, exiting"
  exit 1
fi

for f in $(find $OCI/blobs/sha256 -type f); do
    if ! file "$f" | grep -q "gzip"; then
        continue
    fi
    
    echo "Checking $f"
    tar -tzf $f | sort | uniq -dc
done