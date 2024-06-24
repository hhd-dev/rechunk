import fnmatch
import logging
from typing import Any

import numpy as np
import os
import yaml

from rechunk.model import Package, MetaPackage

from .fedora import get_packages
from .model import Package
from .utils import get_files, get_update_matrix, tqdm

from .ostree import get_ostree_map, dump_ostree_packages

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
    max_layers -= len(dedi_layers)
    assert (
        max_layers > 0
    ), "No layers left after dedicated packages (set dedicated=False for some packages in meta.yml)."

    # Handle the rest of the layers
    pbar = tqdm(total=max_layers, desc="Initial layer fill")
    layers = []
    curr = []
    l_upd = np.zeros(n_segments, dtype=np.bool)
    l_size = 0
    while todo:
        # We will fill layers in two steps:
        # If the layer is emptly, we will insert the largest package
        # in todo.
        # Afterwards, we will insert the package that will cause the
        # minimal bandwidth increase.
        #
        # There will be packages left over in the end, which will be handled
        # differently.

        if not curr:
            p = max(todo, key=lambda p: p.size)
            todo.pop(p)
            curr.append(p)
            l_upd |= upd_matrix[p.index]
            l_size += p.size
        elif l_size > fill_size:
            layers.append(curr)
            logger.info(
                f"Layer {dedi+len(layers):2d}: {l_size / 1e9:.3f} GB with {len(curr):3d} packages."
            )
            if len(layers) >= max_layers:
                break
            curr = []
            l_upd = np.zeros(n_segments, dtype=np.bool)
            l_size = 0
            pbar.update(1)
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
    result_fn: str = "./results.txt",
):
    COMPRESSION_RATIO = 12 / 4.6  # This is for bazzite
    DEDI_RATIO = 0.25  # Assume dedicated layers update a quarter of the time

    n_segments = upd_matrix.shape[1]

    # Update matrix for each layer
    layer_upd = [np.zeros(n_segments, dtype=np.bool) for _ in range(len(layers))]
    for l in layers:
        for p in l:
            layer_upd[layers.index(l)] |= upd_matrix[p.index]

    # Bandwidth calc
    total_bw = 0
    for i, l in enumerate(layers):
        total_bw += np.sum(layer_upd[i]) * sum([p.size for p in l])
    for l in dedi_layers:
        total_bw += np.sum([p.size for p in l]) * n_segments * DEDI_RATIO

    with open(result_fn, "w") as f:
        # Detailed package breakdown and frequency analysis
        logger.info(f"Dedicated layers:")
        f.write("Dedicated layers:\n")
        for i, l in enumerate(dedi_layers):
            data = f"{i+1:3d}: (pkg: {len(l):3d}, mb: {sum([p.size for p in l]) / 1e6 / COMPRESSION_RATIO:3.0f}): {l[0].name}"
            f.write(data + "\n")
            f.write(str([p for p in l[0].nevra]) + "\n")
            logger.info(data)

        logger.info(f"Packages in layers (sorted by frequency):")
        for i, l in sorted(
            enumerate(layers), key=lambda x: -float(np.sum(layer_upd[x[0]]))
        ):
            data = f"{i+1:3d}: (freq: {np.sum(layer_upd[i]):3d}, mb: {sum([p.size for p in l]) / 1e6 / COMPRESSION_RATIO:3.0f}, pkg: {len(l):3d})"
            logger.info(data)
            f.write(data + "\n")
            f.write(str([p.name for p in l]) + "\n")

    # # Condensed results
    # log = f"Final layer fill:\n"
    # for i, (l, pl) in enumerate(zip(layers, prefill_layers)):
    #     log += f"Layer {i+1:2d}: {sum([p.size for p in l]) / 1e6:3.0f} MB "
    #     log += f"(compr. {sum([p.size for p in l]) / 1e6 / COMPRESSION_RATIO:3.0f}) with {len(l):3d}"
    #     if len(pl) != len(l):
    #         log += f" packages (prev {sum([p.size for p in pl]) / 1e6:3.0f} MB with {len(pl):3d}).\n"
    #     else:
    #         log += " packages.\n"
    # logger.info(log)

    logger.info(
        f"Total per update (uncompressed): {total_bw / (n_segments * 1e9):.3f} GB.\n"
        + f"Total per update (compressed): {total_bw / (n_segments * 1e9) / COMPRESSION_RATIO:.3f} GB.\n"
        + f"Layers changed per update: {np.sum([np.sum(u) for u in layer_upd]) / n_segments + len(dedi_layers):.1f}."
    )


def process_meta(
    meta: dict[str, Any], files: dict[str, int], packages: list[Package]
) -> tuple[dict[str, str], list[MetaPackage]]:
    mapping = {}
    remaining_files = dict(files)
    remaining_packages = {p.nevra: p for p in packages}
    new_packages = []

    for name, contents in meta.items():
        meta_files = []
        meta_packages = {}
        for file_pat in contents.get("files", []):
            meta_files.extend(fnmatch.filter(files.keys(), file_pat))
        for pkg_pat in contents.get("packages", []):
            for nevra in fnmatch.filter(remaining_packages.keys(), pkg_pat):
                pkg = remaining_packages.pop(nevra, None)
                if pkg:
                    meta_files.extend([f.name for f in pkg.files])
                    meta_packages[nevra] = None

        total_size = 0
        added_files = False
        for fn in meta_files:
            if fn not in mapping and fn in remaining_files:
                mapping[fn] = name
                s = remaining_files.pop(fn, 0)
                added_files = True
            total_size += s

        if added_files:
            # Only add if it has files to prevent wasting layers
            new_packages.append(
                MetaPackage(
                    index=len(new_packages),
                    name=name,
                    nevra=tuple(meta_packages.keys()),
                    size=total_size,
                    dedicated=contents.get("dedicated", True),
                )
            )

    # Group different variants of packages together
    remaining_names = [p.name for p in remaining_packages.values()]
    for name in remaining_names:
        new_size = 0
        added_nevra = []
        updates = []
        for pkg in remaining_packages.values():
            if pkg.name != name:
                continue
            added_nevra.append(pkg.nevra)
            updates.extend(pkg.updates)
            for f in pkg.files:
                fn = f.name
                if fn not in mapping and fn in remaining_files:
                    mapping[f.name] = name
                    new_size += remaining_files.pop(fn, 0)

        for nevra in added_nevra:
            remaining_packages.pop(nevra, None)

        new_packages.append(
            MetaPackage(
                index=len(new_packages),
                name=name,
                nevra=tuple(added_nevra),
                size=new_size,
                updates=tuple(updates),
                dedicated=False,
            )
        )

    # Add remaining files to unpackaged
    for fn, s in remaining_files.items():
        if fn not in mapping:
            mapping[fn] = "unpackaged"
    new_packages.append(
        MetaPackage(
            index=len(new_packages),
            name="unpackaged",
            nevra=("unpackaged",),
            size=sum(remaining_files.values()),
            dedicated=True,
        )
    )

    return mapping, new_packages


def load_previous_manifest(fn: str, packages: list[MetaPackage], max_layers: int):
    with open(fn, "r") as f:
        raw = f.readlines()

    # Process previous manifest
    todo = dict.fromkeys(packages)
    dedi_layers = []
    used_packages = set()
    log = ""
    prefill = []
    for line in raw:
        layer = []
        logger.info(log)
        log = ""
        for name in line.split(","):
            name = name.strip().replace("meta:", "")
            if name == "null" or not name:
                continue
            log += f"{name}, "

            pkg = None
            for p in todo:
                if p.name == name:
                    pkg = p
                    break

            if pkg is None:
                logger.warning(f"Package '{name}' was removed.")
                continue

            todo.pop(pkg, None)

            if pkg.dedicated:
                dedi_layers.append([pkg])
                logger.info(
                    f"Layer {len(dedi_layers)+len(prefill)}: Dedicated layer for meta '{pkg.name}'."
                )
            else:
                layer.append(pkg)
            used_packages.add(pkg)

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

    return todo, dedi_layers, prefill


def main():
    # Hardcode for now
    dir = "./tree"
    ostree = "./tree.ls"
    meta_fn = "./meta.yml"
    layerdata_fn = "./layerdata.txt"
    max_layers = 40
    prefill_ratio = 0.5
    max_layer_ratio = 1.3

    with open(meta_fn, "r") as f:
        meta = yaml.safe_load(f)["meta"]

    ostree_map, ostree_hash = get_ostree_map(ostree)

    # File analysis of treeusing root perms
    logger.info(f"Beginning analysis.")
    logger.info(f"Scanning directory '{dir}' for files.")
    files = get_files(dir)
    logger.info(f"Found {len(files)} files.")
    logger.info("Getting packages.")
    packages = get_packages(dir)
    logger.info(f"Found {len(packages)} packages.")

    # Repackage using meta file
    mapping, new_packages = process_meta(meta, files, packages)

    logger.info(f"Created {len(new_packages)} meta packages.")

    # Size results
    total_size = sum(files.values())
    package_size = sum([p.size for p in packages])
    new_package_size = sum([p.size for p in new_packages])
    unpackage_size = total_size - package_size

    log = f"Size analysis:"
    log += f"\n -   Packages: {package_size / 1e9:.3f} GB."
    log += f"\n - Unpackaged: {unpackage_size / 1e9:.3f} GB."
    log += f"\n -      Total: {total_size / 1e9:.3f} GB."
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
    upd_matrix = get_update_matrix(new_packages)
    logger.info(f"Update matrix shape: {upd_matrix.shape}.")

    if os.path.exists(layerdata_fn):
        logger.info("Loading existing layer data.")
        todo, dedi_layers, prefill = load_previous_manifest(
            layerdata_fn, new_packages, max_layers
        )
    else:
        logger.warning("No existing layer data. Expect layer shifts")
        todo, dedi_layers, prefill = prefill_layers(
            new_packages, upd_matrix, max_layers, prefill_size
        )

    logger.info(
        f"Leftover packages: {len(todo)}/{len(packages)} with a size of {sum([p.size for p in todo]) / 1e9:.3f} GB."
    )
    logger.info("Filling layers.")
    layers = fill_layers(todo, prefill, upd_matrix, max_layer_size=max_layer_size)

    print_results(dedi_layers, prefill, layers, upd_matrix)

    dump_ostree_packages(
        dedi_layers, layers, "./contentmeta.json", mapping, ostree_map, ostree_hash
    )