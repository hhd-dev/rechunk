#!/usr/bin/env bash

podman unmount --all
podman rm --all
sudo podman unmount --all
sudo podman rm --all

buildah unmount --all
buildah rm --all
sudo buildah unmount --all
sudo buildah rm --all