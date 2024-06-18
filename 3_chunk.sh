#!/usr/bin/env bash

if [ $(id -u) -ne 0 ]; then
    echo "Run as superuser"
    exit 1
fi

if [ -z "$OUT_NAME" ]; then
    echo "OUT_NAME is empty"
    exit 1
fi

if [ -z "$OUT_REF" ]; then
    echo "OUT_REF is empty"
    exit 1
fi

PREV_ARG=""
if [ -z "$PREV_NAME" ]; then
    echo "Warning: PREV_NAME is empty. Will not use previous build to avoid layer shifts."
else
    echo "Using previous manifest $PREV_NAME to avoid layer shifts"
    PREV_ARG="--previous-build-manifest ${PREV_NAME}.manifest.raw.json"
fi

# This file creates a container based on the ostree repository
# with tag $OUT_TAG
MAX_LAYERS=${MAX_LAYERS:=40}
OUT_TAG=${OUT_TAG:=master}
RPM_OSTREE=${RPM_OSTREE:=rpm-ostree}

echo Creating archive with ref ${OUT_REF}
${RPM_OSTREE} compose \
    container-encapsulate \
    --repo=repo ${OUT_TAG} \
    --max-layers ${MAX_LAYERS} \
    --write-contentmeta-json ${OUT_NAME}.contentmeta.json \
    ${PREV_ARG} \
    ${OUT_REF}

echo Created archive with ref ${OUT_REF}
echo Writing manifests to $OUT_NAME.manifest.json, $OUT_NAME.manifest.raw.json
skopeo inspect ${OUT_REF} > ${OUT_NAME}.manifest.json
skopeo inspect --raw ${OUT_REF} > ${OUT_NAME}.manifest.raw.json