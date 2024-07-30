import datetime
import logging
import os
import sys
from datetime import datetime
from typing import Sequence

import numpy as np
from tqdm.auto import tqdm as tqdm_orig

from .model import MetaPackage

logger = logging.getLogger(__name__)

PBAR_OFFSET = 8
PBAR_FORMAT = (" " * PBAR_OFFSET) + ">>>>>>>  {l_bar}{bar}{r_bar}"
VERSION_TAG = "org.opencontainers.image.version"


class tqdm(tqdm_orig):
    def __init__(self, *args, **kwargs):
        kwargs["bar_format"] = PBAR_FORMAT
        super().__init__(*args, **kwargs)


def get_default_meta_yaml():
    """Returns the yaml data of a file in the relative dir provided."""
    import inspect
    import os

    script_fn = inspect.currentframe().f_back.f_globals["__file__"]  # type: ignore
    dirname = os.path.dirname(script_fn)
    return os.path.join(dirname, "meta.yml")


def run(cmd: str, chroot_dir: str | None = None):
    import os
    import subprocess

    args = ["bash", "-c", cmd]
    if chroot_dir:
        args = ["chroot", chroot_dir, *args]
    if os.geteuid() != 0:
        args = ["sudo", *args]

    return subprocess.run(args, stdout=subprocess.PIPE).stdout.decode("utf-8")


def run_nested(cmd: str, dir: str):
    return run(cmd, chroot_dir=dir)


def get_files(dir: str):
    if os.getuid() == 0:
        # Read the dir directly to enable progress bar
        # and skip IPC and to string conversion
        pbar = tqdm(total=300_000, desc="Reading files")
        inodes = set()
        all_files = {}
        for root, _, files in os.walk(dir):
            if "/sysroot/ostree" in root:
                continue
            if "/.build-id/" in root:
                continue

            for file in files:
                fn = os.path.join(root, file)
                if os.path.islink(fn):
                    s = 0
                else:
                    stat = os.stat(fn, follow_symlinks=True)
                    st_size = stat.st_size
                    st_ino = stat.st_ino
                    if st_ino in inodes:
                        s = 0
                    else:
                        s = st_size
                        inodes.add(st_ino)

                # remove leading dot
                all_files[fn[len(dir) :]] = s
                pbar.update(1)
        pbar.close()
    else:
        all_files = {}

        for line in run(f"'{sys.executable}' -m rechunk.walker '{dir}'").splitlines():
            idx = line.index(" ")
            size = int(line[:idx])
            name = line[idx + 1 :]
            all_files[name] = size

    return all_files


def get_update_matrix(packages: list[MetaPackage], biweekly: bool = True):
    # Update matrix for packages
    # For each package, it lists the times it was updated last year
    # The frequency is bi-weekly, assuming that a distro might update 2x
    # per week.
    if biweekly:
        n_segments = 106
    else:
        n_segments = 53
    p_upd = np.zeros((len(packages), n_segments), dtype=np.bool)

    pkg_nochangelog = []
    curr = datetime.now()
    for p in packages:
        i = p.index
        for u in p.updates:
            if (curr - u).days > 365:
                continue

            _, w, d = u.isocalendar()
            if biweekly:
                p_upd[i, 2 * w + (d >= 4)] = 1
            else:
                p_upd[i, w] = 1

        # Some packages have no changelog, assume they always update
        # Use updates from all previous years from this. Some packages
        # may have not updated last year.
        if len(p.updates) <= 2:
            p_upd[i] = 1
            # Dedicated packages we do not care for
            if not p.dedicated:
                pkg_nochangelog.append(p.name)

    logger.info(
        f"Found {len(pkg_nochangelog)} packages with no changelog:\n{str(sorted(pkg_nochangelog))}"
    )

    return p_upd


def get_labels(
    labels: Sequence[str], version: str | None, prev_manifest, version_fn: str | None
) -> tuple[dict[str, str], str]:
    # Date format is YYMMDD
    # Timestamp format is YYYY-MM-DDTHH:MM:SSZ
    now = datetime.now()
    date = now.strftime("%y%m%d")
    timestamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    prev_labels = prev_manifest.get("Labels", {}) if prev_manifest else {}
    prev_version = prev_labels.get(VERSION_TAG, None) if prev_labels else None
    prev_versions = prev_manifest.get("RepoTags", []) if prev_manifest else []

    new_labels = {}
    if version:
        version = version.replace("<date>", date)

        if version != prev_version and version not in prev_versions:
            new_version = version
        else:
            for i in range(1, 10):
                new_version = f"{version}.{i}"
                if new_version not in prev_versions:
                    break

        logger.info(f"New version: '{new_version}'")
        new_labels[VERSION_TAG] = new_version
        if prev_version:
            logger.info(f"Previous version: '{prev_version}'")

        # Write version to file
        if version_fn:
            with open(version_fn, "w") as f:
                f.write(new_version)

    if labels:
        for line in labels:
            if not "=" in line:
                continue
            line = line.strip("\n ")
            idx = line.index("=")
            key = line[:idx]
            value = line[idx + 1 :]
            if "<date>" in value:
                value = value.replace("<date>", date)
            if "<timestamp>" in value:
                value = value.replace("<timestamp>", timestamp)
            new_labels[key] = value

    log = "Writing labels:\n"
    for key, value in new_labels.items():
        log += f" - {key} =\n'{value}'\n"
    logger.info(log)

    return new_labels, timestamp
