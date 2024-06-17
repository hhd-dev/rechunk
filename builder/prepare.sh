#!/usr/bin/env bash

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

podman build --tag 'fedora_build' $SCRIPT_DIR --build-arg="UID=${UID}" --build-arg="GID=${UID}"