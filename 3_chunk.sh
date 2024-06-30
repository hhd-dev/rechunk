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
set -e

# This file creates a container based on the ostree repository
# with tag $OUT_TAG
# MAX_LAYERS=${MAX_LAYERS:=40}
OUT_TAG=${OUT_TAG:=master}
CONTENT_META=${CONTENT_META:="$OUT_NAME.contentmeta.json"}
REPO=${REPO:=./repo}
PREV_MANIFEST=${PREV_MANIFEST:=./${PREV_NAME}.manifest.json}

if [ -n "$PREV_REF" ]; then
    echo "PREV_REF is set, downloading manifest"
    skopeo inspect docker://${PREV_REF} > $PREV_MANIFEST
fi

# Try to use venv if it exists for
# debug builds
if [[ -f venv/bin/rechunk ]]; then
    RECHUNK=${RECHUNK:=venv/bin/rechunk}
else
    RECHUNK=rechunk
fi

PREV_ARG=""
if [ -f "$PREV_MANIFEST" ]; then
    PREV_ARG="--previous-manifest $PREV_MANIFEST"
fi
if [ -n "$MAX_LAYERS" ]; then
    PREV_ARG="$PREV_ARG --max-layers $MAX_LAYERS"
fi
if [ -n "$PREFILL_RATIO" ]; then
    PREV_ARG="$PREV_ARG --prefill-ratio $PREFILL_RATIO"
fi
if [ -n "$LABELS" ]; then
    for label in $LABELS; do
        PREV_ARG="$PREV_ARG --label $label"
    done
fi

$RECHUNK -r "$REPO" -b "$OUT_TAG" -c "$CONTENT_META" $PREV_ARG

PREV_ARG=""
if [ -n "$SKIP_COMPRESSION" ]; then
    PREV_ARG="$PREV_ARG --compression-fast"
fi

echo Creating archive with ref ${OUT_REF}
ostree-ext-cli \
    container encapsulate \
    --repo "${REPO}" "${OUT_TAG}" \
    --contentmeta "${CONTENT_META}" \
    ${PREV_ARG} "${OUT_REF}"

echo Created archive with ref ${OUT_REF}
echo Writing manifests to $OUT_NAME.manifest.json, $OUT_NAME.manifest.raw.json
skopeo inspect ${OUT_REF} > ${OUT_NAME}.manifest.json
skopeo inspect --raw ${OUT_REF} > ${OUT_NAME}.manifest.raw.json

# Reset perms to make the files usable
chmod 666 -R ${OUT_NAME}*