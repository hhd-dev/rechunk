#!/usr/bin/env bash
# This file creates a container based on the ostree repository
# with tag $OUT_TAG

IMAGE=ghcr.io/ublue-os/bazzite-deck
TAG=40-20240616
MAX_LAYERS=80

# e.g., bazzite-deck
IMAGE_NAME=$(echo $IMAGE | rev | cut -d'/' -f1 | rev)
OUT_TAG=${IMAGE_NAME}_${TAG}
OUT_NAME=${OUT_TAG}.oci-archive

rpm-ostree compose \
    container-encapsulate \
    --repo=repo ${OUT_TAG} \
    --max-layers ${MAX_LAYERS} \
    oci-archive:${OUT_NAME}