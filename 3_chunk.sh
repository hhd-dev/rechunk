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
PREV_NAME=${PREV_NAME:=previous}
PREV_MANIFEST=${PREV_MANIFEST:=./${PREV_NAME}.manifest.json}

if [ -n "$PREV_REF" ]; then
    echo "PREV_REF is set, downloading manifest"
    for i in $(seq 1 5); do
        skopeo inspect docker://${PREV_REF} > $PREV_MANIFEST && break
        echo "Failed to download previous manifest, retrying in 3 seconds"
        sleep 3
    done

    if [ ! -f "$PREV_MANIFEST" ]; then
        echo "############################################"
        echo "ERROR: Failed to download previous manifest"
        if [ -n "$PREV_REF_FAIL" ]; then
            echo "Failing build due to PREV_REF_FAIL being set."
            exit 1
        else
            echo "Continuing build without previous manifest"
        fi
    fi
fi

# Try to use venv if it exists for
# debug builds
if [[ -f venv/bin/rechunk ]]; then
    RECHUNK=${RECHUNK:=venv/bin/rechunk}
else
    RECHUNK=rechunk
fi

PREV_ARG=()
if [ -f "$PREV_MANIFEST" ]; then
    PREV_ARG+=("--previous-manifest" "$PREV_MANIFEST")
fi
if [ -n "$MAX_LAYERS" ]; then
    PREV_ARG+=("--max-layers" "$MAX_LAYERS")
fi
if [ -n "$PREFILL_RATIO" ]; then
    PREV_ARG+=("--prefill-ratio" "$PREFILL_RATIO")
fi
if [ -n "$VERSION" ]; then
    PREV_ARG+=("--version" "$VERSION")
fi
if [ -n "$VERSION_FN" ]; then
    PREV_ARG+=("--version-fn" "$VERSION_FN")
fi
if [ -n "$PRETTY" ]; then
    PREV_ARG+=("--pretty" "$PRETTY")
fi
if [ -n "$CHANGELOG" ]; then
    PREV_ARG+=("--changelog" "$CHANGELOG")
fi
if [ -n "$GIT_DIR" ]; then
    PREV_ARG+=("--git-dir" "$GIT_DIR")
fi
if [ -n "$REFISION" ]; then
    PREV_ARG+=("--revision" "$REVISION")
fi

LABEL_ARR=()
if [ -n "$LABELS" ]; then
    IFS=$'\n'
    for label in $LABELS; do
        if [ -z "$label" ]; then
            continue
        fi
        LABEL_ARR+=("--label" "$label")
    done
    unset IFS
fi
if [ -n "$DESCRIPTION" ]; then
    echo "Writing description to 'org.opencontainers.image.description'"
    LABEL_ARR+=("--label" "org.opencontainers.image.description=$DESCRIPTION")  
fi

$RECHUNK -r "$REPO" -b "$OUT_TAG" -c "$CONTENT_META" \
    --changelog-fn "${OUT_NAME}.changelog.txt" \
    "${PREV_ARG[@]}" "${LABEL_ARR[@]}"


PREV_ARG=""
if [ -n "$SKIP_COMPRESSION" ]; then
    echo Warning! Skipping compression
    PREV_ARG="$PREV_ARG --compression-fast"
fi

echo Creating archive with ref ${OUT_REF}
ostree-ext-cli \
    container encapsulate \
    --repo "${REPO}" "${OUT_TAG}" \
    --contentmeta "${CONTENT_META}" \
    ${PREV_ARG} "${OUT_REF}"

echo Created archive with ref ${OUT_REF}

echo Writing manifest to ./$OUT_NAME.manifest.json
skopeo inspect ${OUT_REF} > ${OUT_NAME}.manifest.json

# Reset perms to make the files usable
chmod 666 -R ${OUT_NAME}*