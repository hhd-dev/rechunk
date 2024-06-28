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
CONTENT_META=${CONTENT_META:=contentmeta.json}

# Try to use venv if it exists for
# debug builds
if [[ -f venv/bin/rechunk ]]; then
    RECHUNK=${RECHUNK:=venv/bin/rechunk}
else
    RECHUNK=rechunk
fi
$RECHUNK
cp results.txt ${OUT_NAME}.results.txt

echo Creating archive with ref ${OUT_REF}
ostree-ext-cli \
    container encapsulate \
    --repo=repo ${OUT_TAG} \
    --contentmeta ${CONTENT_META} \
    ${OUT_REF}

echo Created archive with ref ${OUT_REF}
echo Writing manifests to $OUT_NAME.manifest.json, $OUT_NAME.manifest.raw.json
skopeo inspect ${OUT_REF} > ${OUT_NAME}.manifest.json
skopeo inspect --raw ${OUT_REF} > ${OUT_NAME}.manifest.raw.json
cat ${OUT_NAME}.manifest.json | jq -r '.LayersData[].Annotations."ostree.components"' > ${OUT_NAME}.layerdata.txt
cp ${OUT_NAME}.layerdata.txt layerdata.txt

# Reset perms to make the files usable
chmod 666 -R ${OUT_NAME}*