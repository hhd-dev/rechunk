# Bazzite Deck Rechunked (from 40-20240728)
## Version: rc40-20240728.1

Major Components:
  - Kernel: 6.9.9-206.fsync.fc40
  - Gamescope: 100.3.14.24-19.bazzite
  - KDE: 6.1.3

Handheld Daemon:
  - HHD: 3.3.4
  - Adjustor: 3.4.2
  - HHD-UI: 3.2.0

Changes since last version (rc40-20240726.5):
- **[d94536e](https://github.com/hhd-dev/rechunk/commit/d94536e2acb0ca5bb6f7c5cacd35a21c0a25bb82)** switch from tree hashes to commit hashes
- **[92afe86](https://github.com/hhd-dev/rechunk/commit/92afe86aed4d627a15d46e1e9788ae4c80240f8f)** switch unescape method
- **[3b8e892](https://github.com/hhd-dev/rechunk/commit/3b8e8927eb2558ea36e0eadd6e3c3cadca4c094b)** put added packages first
- **[ddf0c6c](https://github.com/hhd-dev/rechunk/commit/ddf0c6c79d15f84f85b789ccb381de9fd9cf4dac)** fix formatter new lines
- **[b88b34c](https://github.com/hhd-dev/rechunk/commit/b88b34c82fffdedbe218f62ca5176d4d6ea6f2a3)** add formatter overrides in action
- **[b82625a](https://github.com/hhd-dev/rechunk/commit/b82625a86f8e9a56e77af2efcda6d45cfa99a92d)** bump minimum dedicated layer size
- **[cdd1b0b](https://github.com/hhd-dev/rechunk/commit/cdd1b0b1493571d6904e67f9aa619b60f64e0a58)** tweak wording
- **[75607d6](https://github.com/hhd-dev/rechunk/commit/75607d644cae0b37a7cee43273c7af1f6deb8deb)** fixup clear plan
- **[1e74e9b](https://github.com/hhd-dev/rechunk/commit/1e74e9b476b4f52476b956e912656059c6605a5a)** add tag disclaimer
- **[7ea2b8b](https://github.com/hhd-dev/rechunk/commit/7ea2b8b8f54843d3cff31ebb91ddafd526e0ed3c)** fix fetch depth
- **[51f8bb6](https://github.com/hhd-dev/rechunk/commit/51f8bb6d0ea7dd0f8d6563dd5cf6fda21b837ebe)** add git to containerfile
- **[abda1e0](https://github.com/hhd-dev/rechunk/commit/abda1e0ba70d66c858bbf74fadf64a4e84abdf6e)** add clear plan parameter
- **[7bcb8a4](https://github.com/hhd-dev/rechunk/commit/7bcb8a45b31717b89b171c1bee7a0aa6e8151ae5)** fix typo

Package Changes:
- **python3-typer** Added at 0.9.0
- **python3-gbulb** Added at 0.6.4
- **python3-ujson** Added at 5.9.0
- **yafti** Added at 0.8.0
- **topgrade** Added at 15.0.0
- **hplip-common** 3.23.12 → 3.24.4
- **libtirpc** 1.3.4 → 1.3.5
- **cups-libs** 2.4.10-1.fc40 → 2.4.10-3.fc40
- **cups-client** 2.4.10-1.fc40 → 2.4.10-3.fc40
- **cups-filesystem** 2.4.10-1.fc40 → 2.4.10-3.fc40
- **cups-ipptool** 2.4.10-1.fc40 → 2.4.10-3.fc40
- **hplip-libs** 3.23.12 → 3.24.4
- **libsane-hpaio** 3.23.12 → 3.24.4
- **cups** 2.4.10-1.fc40 → 2.4.10-3.fc40
- **hplip** 3.23.12 → 3.24.4
- **libva-intel-media-driver** 24.1.5 → 24.2.5
- **kernel-tools-libs** 6.9.10 → 6.9.11
- **kernel-tools** 6.9.10 → 6.9.11
- **python3-pydantic** 2.8.2 → 1.10.2
- **tailscale** 1.70.0-1 → 1.70.0-1.fc40
- **rocm-comgr** 17.1 → 17.3
- **lxc-libs** 5.0.3 → 6.0.1
- **lxc-templates** 5.0.3 → 6.0.1
- **lxc** 5.0.3 → 6.0.1
- **rocm-device-libs** 17.2 → 17.3
- **libglibutil** 1.0.76 → 1.0.79
- **libgbinder** 1.1.36 → 1.1.40
- **hsakmt** 1.0.6-38.rocm6.0.0.fc40 → 1.0.6-39.rocm6.1.1.fc40
- **rocm-runtime** 6.0.0 → 6.1.2
- **rocminfo** 6.0.2 → 6.1.1
- **hipcc** 6.0.2 → 17.3
- **rocm-hip** 6.0.2 → 6.1.2
- **rocm-opencl** 6.0.2 → 6.1.2
- **rocm-clinfo** 6.0.2 → 6.1.2
- **adjustor** 3.4.1 → 3.4.2
- **hhd** 3.3.3 → 3.3.4
- **gamescope-session-plus** 0.0.git.283.bb3fa35b → 0.0.git.296.b71fc7c5
- **systemd-devel** 255.8 → Removed
- **python3-annotated-types** 0.7.0 → Removed
- **libevdev-devel** 1.13.2 → Removed
- **python3-pydantic-core** 2.20.1 → Removed
- **python3-pydantic+email** 2.8.2 → Removed
- **joycond** 0.0.git.115.f13982c1 → Removed
- **clang-resource-filesystem** 18.1.6 → Removed

