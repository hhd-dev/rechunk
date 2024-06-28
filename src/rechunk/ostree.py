import json
import logging

from .model import MetaPackage

logger = logging.getLogger(__name__)

def get_ostree_map(fn: str):
    # Prefix has a fixed length
    # unless filesize is larger than what fits
    prefix = len("d00555 0 0")
    hash_len = 64

    mapping = {}
    hashes = {}
    with open(fn, "r") as f:
        for line in f.readlines():
            # Skip directories and soft links
            if line[0] == "d":
                continue

            ofs = prefix - 1
            # Link count
            while line[ofs] != " ":
                ofs += 1
            # Space after
            while line[ofs] == " ":
                ofs += 1
            # Size
            while line[ofs] != " ":
                ofs += 1

            fhash = line[ofs + 1 : ofs + 65]
            assert " " not in fhash, f"Hash fail: {fhash} | {line}"
            if line[0] == "l":
                end_i = line.rindex("->")
            else:
                end_i = -1
            fn = line[ofs + hash_len + 1 : end_i].strip()
            mapping[fn] = fhash
            hashes[fhash] = None

    return mapping, hashes


def dump_ostree_packages(
    dedi_layers: list[list[MetaPackage]],
    layers: list[list[MetaPackage]],
    out_fn: str,
    mapping: dict[str, str],
    ostree_map: dict[str, str],
    ostree_hashes: dict[str, None],
):
    # Create layer meta
    ostree_hashes = dict(ostree_hashes)
    smeta = {}
    pkg_to_layer = {}

    def get_pkg_name(pkg: MetaPackage):
        return f"meta:{pkg.name}" if pkg.meta else pkg.name

    for layer in dedi_layers:
        layer_name = f"dedi:{get_pkg_name(layer[0])}"
        layer_human = layer_name

        unpackaged = len(layer) == 1 and "unpackaged" in layer[0].name
        if unpackaged:
            layer_name = "unpackaged"
            layer_human = "dedi:meta:unpackaged"

        smeta[layer_name] = layer_name
        for pkg in layer:
            pkg_to_layer[pkg.name] = layer_name

    for i, layer in enumerate(layers):
        layer_name = f"rechunk_layer{i:03d}"
        layer_human = ",".join([get_pkg_name(pkg) for pkg in layer])

        unpackaged = len(layer) == 1 and "unpackaged" in layer[0].name
        if unpackaged:
            layer_name = "unpackaged"
        smeta[layer_name] = layer_human

        for pkg in layer:
            pkg_to_layer[pkg.name] = layer_name

    if "unpackaged" not in smeta:
        logger.info("No unpackaged layer found. Creating it manually.")
        smeta["unpackaged"] = "dedi:meta:unpackaged"

    # Create mappings
    ostree_out = {}
    used_layers = set()
    for fn, pkg in mapping.items():
        layer = pkg_to_layer[pkg]
        if fn.startswith("/etc") or fn.startswith("/usr/etc"):
            # Multiple packages can own the same etc file
            # and they may be modified. Avoid breaking layer caching.
            continue
        if fn in ostree_map:
            fhash = ostree_map[fn]
            if fhash in ostree_hashes:
                # First layer to get hash owns it
                ostree_hashes.pop(fhash, None)
                ostree_out[fhash] = layer
                used_layers.add(layer)

    for fhash in ostree_hashes:
        ostree_out[fhash] = "unpackaged"
        used_layers.add("unpackaged")

    # Trim layers to avoid empty ones
    final_layers = {k: v for k, v in sorted(smeta.items()) if k in used_layers}

    with open(out_fn, "w") as f:
        json.dump(
            {
                "layers": final_layers,
                "mapping": dict(sorted(ostree_out.items())),
            },
            f,
            indent=2,
        )


if __name__ == "__main__":
    print(get_ostree_map("./tree.ls"))
