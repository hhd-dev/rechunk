import fnmatch
import json
import logging
import os
from typing import Any, Sequence, cast

import numpy as np
import yaml

from rechunk.model import MetaPackage, Package

from .fedora import get_packages
from .model import INFO_KEY, Package, get_layers, get_info, ExportInfo
from .ostree import (
    calculate_ostree_layers,
    dump_ostree_contentmeta,
    get_ostree_map,
    run_with_ostree_files,
)
from .utils import get_default_meta_yaml, get_labels, get_update_matrix, tqdm

logger = logging.getLogger(__name__)


def prefill_layers(
    packages: list[MetaPackage],
    upd_matrix: np.ndarray,
    max_layers: int,
    fill_size: int,
):
    layers = []
    logger.info("Prefilling layers.")

    # Use a dict because it maintains order
    # Important for reproducibility
    todo = dict.fromkeys(packages)
    n_segments = upd_matrix.shape[1]

    # Handle dedicated packages
    dedi_layers = []
    dedi = 0
    for p in packages:
        if p.dedicated:
            dedi_layers.append([p])
            logger.info(
                f"Layer {dedi+1:2d}: {p.size / 1e9:.3f} GB, dedicated layer for meta '{p.name}'."
            )
            dedi += 1
            todo.pop(p)

    SIZE_LIMITS = (5e5, 1e6)
    max_layers -= len(dedi_layers)
    assert max_layers > len(
        SIZE_LIMITS
    ), "No layers left after dedicated packages and fine layers (set dedicated=False for some packages in meta.yml)."

    # Handle the rest of the layers
    pbar = tqdm(total=max_layers, desc="Initial layer fill")
    layers = []

    # Add layers for small packages
    # These packages will just ruin the cache
    # in other layers for little benefit
    for size_limit in SIZE_LIMITS:
        fines = []
        for p in packages:
            if p.size < size_limit and p in todo:
                fines.append(p)
                todo.pop(p)
        if fines:
            layers.append(fines)
            logger.info(
                f"Layer {dedi+len(layers):2d}: {sum([p.size for p in fines]) / 1e9:.3f} GB, for small (< {size_limit // 1e6} MB) packages with {len(fines)} packages."
            )
            pbar.update(1)

    curr = []
    l_upd = np.zeros(n_segments, dtype=np.bool)
    l_size = 0
    while True:
        # We will fill layers in two steps:
        # If the layer is emptly, we will insert the largest package
        # in todo.
        # Afterwards, we will insert the package that will cause the
        # minimal bandwidth increase.
        #
        # There will be packages left over in the end, which will be handled
        # differently.

        if l_size > fill_size or not todo:
            if curr:
                # Since this also gets hit with not todo
                # curr might be empty, avoid creating a layer
                layers.append(curr)
                logger.info(
                    f"Layer {dedi+len(layers):2d}: {l_size / 1e9:.3f} GB with {len(curr):3d} packages."
                )
            if len(layers) >= max_layers or not todo:
                break
            curr = []
            l_upd = np.zeros(n_segments, dtype=np.bool)
            l_size = 0
            pbar.update(1)
        elif not curr:
            p = max(todo, key=lambda p: p.size)
            todo.pop(p)
            curr.append(p)
            l_upd |= upd_matrix[p.index]
            l_size += p.size
        else:
            # Calculate the bandwidth increase for each package
            # and select the one with the smallest increase
            b_upd = None
            b_pkg = None
            b_size = 0
            b_bw = 1e24
            for p in todo:
                upd = l_upd | upd_matrix[p.index]
                new_size = l_size + p.size
                bw = np.sum(upd) * new_size
                if bw < b_bw:
                    b_bw = bw
                    b_upd = upd
                    b_pkg = p
                    b_size = new_size

            assert (
                b_pkg is not None and b_upd is not None
            ), "No package selected. How did we get here?"

            todo.pop(b_pkg)
            curr.append(b_pkg)
            l_upd = b_upd
            l_size = b_size

    pbar.update(1)
    pbar.close()
    return todo, dedi_layers, layers


def fill_layers(
    todo: dict[MetaPackage, None],
    layers: list[list[MetaPackage]],
    upd_matrix: np.ndarray,
    max_layer_size: int,
):
    # Fill the layers with the leftover packages
    # We will fill the layers in the same way as before
    # but we will not create new layers.
    # We will insert the package that will cause the
    # minimal bandwidth increase.

    # Make a copy as we will muate
    if not todo:
        return layers
    todo = dict(todo)
    layers = [l.copy() for l in layers]
    pbar = tqdm(total=len(todo), desc="Final layer fill")
    n_segments = upd_matrix.shape[1]

    layer_size = [sum([p.size for p in l]) for l in layers]
    layer_upd = [np.zeros(n_segments, dtype=np.bool) for _ in range(len(layers))]
    for l in layers:
        for p in l:
            layer_upd[layers.index(l)] |= upd_matrix[p.index]
    layer_bw = [float(np.sum(layer_upd[i]) * layer_size[i]) for i in range(len(layers))]

    while todo:
        # There are still some leftover packages.
        # Since we did a heuristic to prefill the layers
        # we left out some space.
        #
        # Now we go back and do a computationally expensive step
        # and insert the packages in the layers that will cause
        # the least bandwidth increase.
        b_layer = None
        b_pkg = None
        b_upd = None
        b_bw = 1e24
        b_bw_total = 0
        for i in range(len(layers)):
            l_size = layer_size[i]
            if l_size > max_layer_size:
                continue
            for p in todo:
                upd = layer_upd[i] | upd_matrix[p.index]
                new_size = l_size + p.size
                bw_total = np.sum(upd) * new_size
                bw = bw_total - layer_bw[i]
                if bw < b_bw:
                    b_bw = bw
                    b_layer = i
                    b_pkg = p
                    b_upd = upd
                    b_bw_total = bw_total

        assert (
            b_layer is not None and b_pkg is not None and b_upd is not None
        ), "No package selected. How did we get here?"

        layers[b_layer].append(b_pkg)
        layer_upd[b_layer] = b_upd
        layer_size[b_layer] += b_pkg.size
        layer_bw[b_layer] = float(b_bw_total)
        todo.pop(b_pkg)
        pbar.update(1)

    pbar.close()
    return layers


def print_results(
    dedi_layers: list[list[MetaPackage]],
    prefill_layers: list[list[MetaPackage]],
    layers: list[list[MetaPackage]],
    upd_matrix: np.ndarray,
    result_fn: str | None = "./results.txt",
):
    COMPRESSION_RATIO = 12 / 4.6  # This is for bazzite
    DEDI_RATIO = 0.4  # Assume dedicated layers update a quarter of the time

    n_segments = upd_matrix.shape[1]

    # Update matrix for each layer
    layer_upd = [np.zeros(n_segments, dtype=np.bool) for _ in range(len(layers))]
    for i, l in enumerate(layers):
        for p in l:
            layer_upd[i] |= upd_matrix[p.index]

    # Bandwidth calc
    total_bw = 0
    for i, l in enumerate(layers):
        total_bw += np.sum(layer_upd[i]) * sum([p.size for p in l])
    for l in dedi_layers:
        total_bw += np.sum([p.size for p in l]) * n_segments * DEDI_RATIO

    # Detailed package breakdown and frequency analysis
    logger.info(f"Dedicated layers:")
    results = "Dedicated layers:\n"
    for i, l in enumerate(dedi_layers):
        data = f"{i+1:3d}: (pkg: {len(l):3d}, mb: {sum([p.size for p in l]) / 1e6 / COMPRESSION_RATIO:3.0f}): {l[0].name}"
        results += data + "\n"
        results += str([p for p in l[0].nevra]) + "\n"
        logger.info(data)

    logger.info(f"Packages in layers (sorted by frequency):")
    results += "Packages in layers (sorted by frequency):\n"
    for i, l in sorted(
        enumerate(layers), key=lambda x: -float(np.sum(layer_upd[x[0]]))
    ):
        data = f"{i+1:3d}: (freq: {np.sum(layer_upd[i]):3d}, mb: {sum([p.size for p in l]) / 1e6 / COMPRESSION_RATIO:3.0f}, pkg: {len(l):3d})"
        logger.info(data)
        results += data + "\n"
        results += (
            str(
                [
                    f"{p.name}: {p.size // 1e6}"
                    for p in sorted(l, key=lambda p: p.size, reverse=True)
                ]
            )
            + "\n"
        )

    if result_fn:
        with open(result_fn, "w") as f:
            f.write(results)

    logger.info(
        f"Total per update (uncompressed): {total_bw / (n_segments * 1e9):.3f} GB.\n"
        + f"Total per update (compressed): {total_bw / (n_segments * 1e9) / COMPRESSION_RATIO:.3f} GB.\n"
        + f"Layers changed per update: {np.sum([np.sum(u) for u in layer_upd]) / n_segments + len(dedi_layers) * DEDI_RATIO:.1f}."
    )


def process_meta(
    meta: dict[str, Any],
    ostree_map: dict[str, str],
    ostree_hash: dict[str, int],
    packages: list[Package],
) -> tuple[dict[str, str], list[MetaPackage]]:
    mapping = {}
    remaining_hashes = dict(ostree_hash)
    remaining_packages = dict.fromkeys(packages)
    new_packages = []
    unpackaged = None

    for name, contents in meta.items():
        meta_files = []
        meta_updates = []
        meta_packages = {}
        for file_pat in contents.get("files", []):
            meta_files.extend(fnmatch.filter(ostree_map.keys(), file_pat))

        # packages of the same name should always be part of
        # the same meta package due to a name collision
        for pkg_pat in [*contents.get("packages", []), name]:
            for pname in fnmatch.filter(
                dict.fromkeys([p.name for p in remaining_packages]), pkg_pat
            ):
                pkgs = [p for p in remaining_packages if p.name == pname]
                for pkg in pkgs:
                    remaining_packages.pop(pkg, None)
                    meta_files.extend([f.name for f in pkg.files])
                    meta_packages[pkg.nevra] = None
                    meta_updates.extend(pkg.updates)

        total_size = 0
        added_files = False
        for fn in meta_files:
            if fn.startswith("/etc") or fn.startswith("/usr/etc"):
                # Skip configuration files, they are small anyway
                # Also, lib32 and lib64 packages use the same file
                continue

            if fn not in ostree_map:
                continue
            ohash = ostree_map[fn]

            if ohash not in remaining_hashes:
                continue

            mapping[ohash] = name
            total_size += remaining_hashes.pop(ohash)
            added_files = True

        if added_files:
            # Only add if it has files to prevent wasting layers
            dedicated = contents.get("dedicated", True)

            if name != "unpackaged" and dedicated and total_size < 10e6:
                # Some times, e.g., a KDE image will include a single gnome package
                # Which will make rechunk make a dedicated layer for it.
                # Force disable dedicated layers if the size is too small.
                logger.warning(
                    f"Meta package '{name}' is too small ({total_size} < 10MB). Disabling dedicated layer."
                )
                dedicated = False

            npkg = MetaPackage(
                index=len(new_packages),
                name=name,
                nevra=tuple(meta_packages.keys()),
                size=total_size,
                updates=tuple(meta_updates),
                dedicated=dedicated,
                meta=True,
            )
            if npkg.name == "unpackaged":
                unpackaged = npkg
            else:
                new_packages.append(npkg)

    # Group different variants of packages together
    remaining_names = dict.fromkeys([p.name for p in remaining_packages])
    for name in remaining_names:
        new_size = 0
        added_pkg = []
        updates = []
        for pkg in remaining_packages:
            if pkg.name != name:
                continue
            added_pkg.append(pkg)
            updates.extend(pkg.updates)
            for f in pkg.files:
                fn = f.name
                if fn.startswith("/etc") or fn.startswith("/usr/etc"):
                    # Skip configuration files, they are small anyway
                    # Also, lib32 and lib64 packages use the same file
                    continue

                if fn not in ostree_map:
                    continue
                ohash = ostree_map[fn]

                if ohash not in remaining_hashes:
                    continue

                mapping[ohash] = name
                new_size += remaining_hashes.pop(ohash)

        for pkg in added_pkg:
            remaining_packages.pop(pkg, None)

        new_packages.append(
            MetaPackage(
                index=len(new_packages),
                name=name,
                nevra=tuple([p.nevra for p in added_pkg]),
                size=new_size,
                updates=tuple(updates),
                dedicated=False,
            )
        )

    # Add remaining files to unpackaged
    for ohash in remaining_hashes:
        mapping[ohash] = "unpackaged"

    if unpackaged is None:
        new_packages.append(
            MetaPackage(
                index=len(new_packages),
                name="unpackaged",
                nevra=("unpackaged",),
                size=sum(remaining_hashes.values()),
                dedicated=True,
                meta=True,
            )
        )
    else:
        new_packages.append(
            MetaPackage(
                index=len(new_packages),
                name="unpackaged",
                nevra=(*unpackaged.nevra, "unpackaged"),
                size=sum(remaining_hashes.values()) + unpackaged.size,
                # updates=unpackaged.updates,
                dedicated=True,
                meta=True,
            )
        )

    hash_to_file = {v: k for k, v in ostree_map.items()}
    log = f"Large remaining files:"
    for hash, size in sorted(
        remaining_hashes.items(), key=lambda x: x[1], reverse=True
    )[:50]:
        if size < 5e5:
            break
        log += f"\n - {size / 1e6:6.3f} MB {hash_to_file[hash]}"
    logger.info(log)

    return mapping, new_packages


def load_previous_manifest(
    fn: str | list[str], packages: list[MetaPackage], max_layers: int
):
    logger.info(f"Loading previous manifest from '{fn}'.")
    info = None

    if isinstance(fn, str):
        with open(fn, "r") as f:
            raw = json.load(f)

        # Since podman/skopeo do not respect layer annotations, use
        # a JSON config key
        info = get_info(raw)
        layers = get_layers(info)

        # Then as a fallback use the old OSTree format
        if layers:
            logger.info(
                f"Processing previous manifest with {len(layers)} layers (loaded from '{INFO_KEY}')."
            )
        else:
            layers = []
            for data in raw["LayersData"]:
                if "Annotations" not in data:
                    continue
                annotations = data["Annotations"]
                if not annotations:
                    continue
                if "ostree.components" not in annotations:
                    continue
                layers.append(annotations["ostree.components"].split(","))
            logger.info(
                f"Processing previous manifest with {len(raw)} layers (loaded from 'ostree.components')."
            )
    else:
        raw = None
        layers = [l.split(",") for l in fn]
        logger.info(
            f"Processing previous manifest with {len(fn)} layers (through cache argument)."
        )

    assert layers, "No layers found in previous manifest. Raising."

    # Process previous manifest
    todo = dict.fromkeys(packages)
    dedi_layers = []
    removed = list()
    prefill = []
    for raw_layer in layers:
        layer = []
        for name in raw_layer:
            name = name.strip().replace("meta:", "").replace("dedi:", "")
            if name == "null" or not name:
                continue

            pkg = None
            for p in todo:
                if p.name == name:
                    if pkg is not None:
                        logger.error(
                            f"Duplicate package '{name}' found in previous manifest."
                        )
                    pkg = p

            if pkg is None:
                removed.append(name)
                continue

            todo.pop(pkg, None)

            if pkg.dedicated:
                dedi_layers.append([pkg])
                logger.info(
                    f"Layer {len(dedi_layers)+len(prefill)}: Dedicated layer for meta '{pkg.name}'."
                )
            else:
                layer.append(pkg)

        if layer:
            logger.info(
                f"Layer {len(dedi_layers)+len(prefill)}: {sum([p.size for p in layer]) // 1e6} MB loaded with {len(layer)} packages."
            )
            prefill.append(layer)

    # Add empty layers for the rest
    for _ in range(len(dedi_layers) + len(prefill) - 1, max_layers):
        prefill.append([])

    if todo:
        logger.info(f"New packages found:\n{[p.name for p in todo]}")
    if removed:
        logger.info(f"The following packages were removed:\n{removed}")

    return todo, dedi_layers, prefill, raw, info


def main(
    repo: str,
    ref: str,
    contentmeta_fn: str | None = None,
    meta_fn: str | None = None,
    previous_manifest: str | list[str] | None = None,
    max_layers: int | None = None,
    prefill_ratio: float | None = None,
    max_layer_ratio: float | None = None,
    biweekly: bool = False,
    result_fn: str | None = "./results.txt",
    labels: Sequence[str] = [],
    version: str | None = None,
    pretty: str | None = None,
    version_fn: str | None = None,
    _cache: dict | None = None,
    revision: str | None = None,
    git_dir: str | None = None,
    changelog: str | None = None,
    changelog_fn: str | None = None,
    clear_plan: bool = False,
    formatters: dict[str, str] = {},
):
    if not meta_fn:
        meta_fn = get_default_meta_yaml()
    with open(meta_fn, "r") as f:
        meta = yaml.safe_load(f)
        if max_layers is None:
            max_layers = cast(int, meta.get("max_layers", 39))
        if prefill_ratio is None:
            prefill_ratio = cast(float, meta.get("layer_prefill_ratio", 0.4))
        if max_layer_ratio is None:
            max_layer_ratio = cast(float, meta.get("layer_max_ratio", 1.3))

    if _cache is not None and ref in _cache:
        # Use cache to speedup experiments
        logger.warning(f"Using cached inmemory data from '{ref}'!")
        ostree_map, ostree_hash, packages = _cache[ref]
    else:
        logger.info(f"Beginning analysis.")
        logger.info(f"Scanning OSTree repo '{repo}' with ref '{ref}' for files.")
        ostree_map, ostree_hash = get_ostree_map(repo, ref)

        # Use the database by pulling it from ostree
        packages = run_with_ostree_files(
            repo, ostree_map, ["/usr/share/rpm/rpmdb.sqlite"], get_packages
        )
        logger.info(f"Found {len(packages)} packages.")
        if _cache is not None:
            _cache[ref] = ostree_map, ostree_hash, packages

    # Repackage using meta file
    mapping, new_packages = process_meta(
        meta["meta"], ostree_map, ostree_hash, packages
    )

    logger.info(f"Created {len(new_packages)} meta packages.")

    # Size results
    total_size = sum(ostree_hash.values())
    package_size = sum([p.size for p in packages])
    new_package_size = sum([p.size for p in new_packages])
    unpackage_size = total_size - package_size

    log = f"Size analysis:"
    log += f"\n -   Packages: {package_size / 1e9:6.3f} GB."
    log += f"\n - Unpackaged: {unpackage_size / 1e9:6.3f} GB."
    log += f"\n -      Total: {total_size / 1e9:6.3f} GB."
    logger.info(log)

    # Calculate plan
    layer_size = total_size / max_layers
    prefill_size = int(layer_size * prefill_ratio)
    max_layer_size = int(layer_size * max_layer_ratio)
    logger.info(
        f"Rechunking into {max_layers} layers. Using:\n"
        + f" - Avg Layer size: {layer_size / 1e9:.3f} GB\n"
        + f" -   Prefill size: {prefill_size / 1e9:.3f} GB\n"
        + f" - Max layer size: {max_layer_size / 1e9:.3f} GB."
    )
    logger.info("Creating update matrix.")
    upd_matrix = get_update_matrix(new_packages, biweekly)
    logger.info(f"Update matrix shape: {upd_matrix.shape}.")

    found_previous_plan = False
    manifest_json = None
    info = None
    if previous_manifest:
        try:
            logger.info("Loading existing layer data.")
            todo, dedi_layers, prefill, manifest_json, info = load_previous_manifest(
                previous_manifest, new_packages, max_layers
            )
            found_previous_plan = True
        except Exception as e:
            logger.error(f"Error loading previous manifest:\n{e}")

    if not found_previous_plan or clear_plan:
        if clear_plan:
            logger.warning("Creating a fresh plan due to --clear-plan.")
        else:
            logger.warning("No existing layer data. Expect layer shifts")
        todo, dedi_layers, prefill = prefill_layers(
            new_packages, upd_matrix, max_layers, prefill_size
        )

    logger.info(
        f"Leftover packages: {len(todo)}/{len(new_packages)} with a size of {sum([p.size for p in todo]) / 1e9:.3f} GB."
    )
    logger.info("Filling layers.")
    # Legacy algorithm simulation
    # prefill[-1] += list(todo.keys())
    # todo = {}
    layers = fill_layers(todo, prefill, upd_matrix, max_layer_size=max_layer_size)
    print_results(dedi_layers, prefill, layers, upd_matrix, result_fn)

    final_layers, ostree_out = calculate_ostree_layers(dedi_layers, layers, mapping)
    new_labels, timestamp = get_labels(
        labels=labels,
        version=version,
        prev_manifest=manifest_json,
        version_fn=version_fn,
        pretty=pretty,
        base_pkg=packages,
        layers=final_layers,
        revision=revision,
        git_dir=git_dir,
        changelog_template=changelog,
        changelog_fn=changelog_fn,
        info=info,
        formatters=formatters,
    )

    if contentmeta_fn:
        dump_ostree_contentmeta(
            final_layers, ostree_out, contentmeta_fn, new_labels, timestamp
        )

    return dedi_layers, layers
