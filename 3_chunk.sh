#!/usr/bin/env bash

if [ $(id -u) -ne 0 ]; then
    echo "Run as superuser"
    exit 1
fi

if [ -z "$OUT_NAME" ]; then
    echo "OUT_NAME is empty"
    exit 1
fi

# This file creates a container based on the ostree repository
# with tag $OUT_TAG
MAX_LAYERS=${MAX_LAYERS:=40}
OUT_TAG=${OUT_TAG:=master}
RPM_OSTREE=${RPM_OSTREE:=rpm-ostree}

echo Creating archive with name $OUT_NAME.oci-archive
${RPM_OSTREE} compose \
    container-encapsulate \
    --repo=repo ${OUT_TAG} \
    --max-layers ${MAX_LAYERS} \
    oci-archive:${OUT_NAME}.oci-archive

echo Created archive with name $OUT_NAME.oci-archive
echo Writing manifest to $OUT_NAME.manifest.json
skopeo inspect oci-archive:${OUT_NAME}.oci-archive > ${OUT_NAME}.manifest.json