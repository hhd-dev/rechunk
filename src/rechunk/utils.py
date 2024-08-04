import datetime
import logging
import os
import subprocess
import sys
from datetime import datetime
from typing import Sequence

import numpy as np
from tqdm.auto import tqdm as tqdm_orig

from .model import INFO_KEY, ExportInfo, MetaPackage, Package, export_v2

logger = logging.getLogger(__name__)

PBAR_OFFSET = 8
PBAR_FORMAT = (" " * PBAR_OFFSET) + ">>>>>>>  {l_bar}{bar}{r_bar}"
VERSION_TAG = "org.opencontainers.image.version"
REVISION_TAG = "org.opencontainers.image.revision"

DEFAULT_FORMATTERS = {
    "commits.none": "-\n",
    "commits.commit": "- **<short>** <subject>\n",
    "pkgupd.none": "-\n",
    "pkgupd.update": " - **<package>**: <old> → <new>\n",
    "pkgupd.add": " - **<package>**: x → <new>\n",
    "pkgupd.remove": " - **<package>**: <old> → x\n",
}


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


def get_commits(
    git_dir: str | None,
    revision: str | None,
    prev_rev: str | None,
    formatters: dict[str, str],
):
    logger.info(f"Getting commits from '{prev_rev}' to '{revision}' in '{git_dir}'")
    if not git_dir or not revision or not prev_rev:
        return ""

    out = ""
    try:
        cmd = f"git --git-dir='{git_dir}/.git' log --format=\"%h/%H/%s\" --no-merges {prev_rev}..{revision}"
        for commit in (
            subprocess.run(cmd, stdout=subprocess.PIPE, shell=True)
            .stdout.decode("utf-8")
            .splitlines()
        ):
            if not "/" in commit:
                continue
            idx = commit.index("/")
            short = commit[:idx]
            rest = commit[idx + 1 :]
            idx = rest.index("/")
            hash = rest[:idx]
            commit = rest[idx + 1 :]
            out += (
                formatters["commits.commit"]
                .replace("<short>", short)
                .replace("<subject>", commit)
                .replace("<hash>", hash)
            )
    except Exception as e:
        logger.error(f"Failed to get commits: {e}")
    return out


def get_package_update_str(
    base_pkg: Sequence[Package] | None,
    info: ExportInfo | None,
    formatters: dict[str, str],
):
    if not base_pkg or not info or not info.get("packages", None):
        return ""

    previous = info.get("packages", {})
    seen = set()

    added = ""
    updated = ""
    for p in base_pkg:
        if p.name in seen:
            continue
        seen.add(p.name)

        if p.name not in previous:
            added += (
                formatters["pkgupd.add"]
                .replace("<new>", p.version)
                .replace("<package>", p.name)
            )
        else:
            pv = previous[p.name]
            # Skip release for package version updates
            if "-" in pv:
                prel = pv[pv.rindex("-") + 1 :]
                pv = pv[: pv.rindex("-")]
            else:
                prel = None

            if p.version != pv:
                prev = pv
                newv = p.version
            elif prel and p.release != prel:
                prev = f"{pv}-{prel}"
                newv = f"{p.version}-{p.release}"
            else:
                continue

            updated += (
                formatters["pkgupd.update"]
                .replace("<old>", prev)
                .replace("<new>", newv)
                .replace("<package>", p.name)
            )

    out = added + updated
    for p in previous:
        if p not in seen:
            pv = previous[p]
            if "-" in pv:
                pv = pv[: pv.rindex("-")]
            out += (
                formatters["pkgupd.remove"].replace("<old>", pv).replace("<package>", p)
            )
        seen.add(p)

    return out


def get_labels(
    labels: Sequence[str],
    version: str | None,
    prev_manifest,
    version_fn: str | None,
    pretty: str | None,
    base_pkg: Sequence[Package] | None,
    layers: dict[str, Sequence[str]],
    revision: str | None,
    git_dir: str | None,
    changelog_template: str | None,
    changelog_fn: str | None,
    info: ExportInfo | None,
    formatters: dict[str, str] = {},
) -> tuple[dict[str, str], str]:
    formatters = {**DEFAULT_FORMATTERS, **formatters}

    # Date format is YYMMDD
    # Timestamp format is YYYY-MM-DDTHH:MM:SSZ
    now = datetime.now()
    date = now.strftime("%y%m%d")
    timestamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    pkgupd = get_package_update_str(base_pkg, info, formatters)

    prev_labels = prev_manifest.get("Labels", {}) if prev_manifest else {}
    prev_version = prev_labels.get(VERSION_TAG, None) if prev_labels else None
    prev_versions = prev_manifest.get("RepoTags", []) if prev_manifest else []
    new_version = None

    new_labels = {}
    if version:
        version = version.replace("<date>", date)

        if version != prev_version and version not in prev_versions:
            new_version = version
        else:
            if len(version) > 3 and version[-2] == ".":
                # remove .X suffix if it exists already
                version = version[:-2]

            # Add our own suffix
            for i in range(1, 10):
                new_version = f"{version}.{i}"
                if new_version not in prev_versions:
                    break

        logger.info(f"New version: '{new_version}'")
        new_labels[VERSION_TAG] = new_version
        if prev_version:
            logger.info(f"Previous version: '{prev_version}'")

        # Write version to file
        if version_fn and new_version:
            with open(version_fn, "w") as f:
                f.write(new_version)

    imginfo = export_v2(
        uniq=new_version,
        base_pkg=base_pkg,
        layers=list(layers.values()),
        revision=revision,
    )
    BLACKLIST_KEY = "> IMGINFO V2 INSERTED"
    new_labels[INFO_KEY] = imginfo
    if revision:
        new_labels[REVISION_TAG] = revision

    blacklist = dict()
    blacklist[INFO_KEY] = BLACKLIST_KEY
    commit_str = get_commits(
        git_dir,
        revision,
        (info or {}).get("revision", None) or prev_labels.get(REVISION_TAG, None),
        formatters=formatters,
    )

    def process_label(key: str, value: str):
        if "<changelog>" in value:
            value = value.replace("<changelog>", changelog_template or "")
        if "<version>" in value and new_version:
            value = value.replace("<version>", new_version)
        if "<date>" in value:
            value = value.replace("<date>", date)
        if "<timestamp>" in value:
            value = value.replace("<timestamp>", timestamp)
        if "<pretty>" in value and pretty:
            value = value.replace("<pretty>", pretty)
        if "<previous>" in value and prev_version:
            value = value.replace("<previous>", prev_version)
        if "<imginfo>" in value:
            value = value.replace("<imginfo>", imginfo)
            blacklist[key] = BLACKLIST_KEY
        if "<commits>" in value:
            value = value.replace("<commits>", commit_str or formatters["commits.none"])
        if "<pkgupd>" in value:
            value = value.replace("<pkgupd>", pkgupd or formatters["pkgupd.none"])

        if base_pkg:
            for pkg in base_pkg:
                if not pkg.version:
                    continue
                vkey = f"<version:{pkg.name}>"
                if vkey in value:
                    value = value.replace(vkey, pkg.version)
                vkey = f"<relver:{pkg.name}>"
                if vkey in value:
                    value = value.replace(
                        vkey,
                        (
                            f"{pkg.version}-{pkg.release}"
                            if pkg.release
                            else pkg.version
                        ),
                    )
        return value

    if changelog_fn:
        chng = process_label("", "<changelog>")
        if chng:
            logger.info(f"Changelog:\n{chng}")
        with open(changelog_fn, "w") as f:
            f.write(chng)

    if labels:
        for line in labels:
            if not "=" in line:
                continue
            line = line.strip("\n ")
            idx = line.index("=")
            key = line[:idx]
            value = line[idx + 1 :]
            new_labels[key] = process_label(key, value)

    if new_labels:
        log = "Writing labels:\n"
        for key, value in new_labels.items():
            if key in blacklist:
                value = blacklist[key]
            log += f" - {key} =\n'{value}'\n"
        logger.info(log)
    else:
        logger.warning("No labels found to write.")

    return new_labels, timestamp
