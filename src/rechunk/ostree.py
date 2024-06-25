from .model import MetaPackage
import json


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
    smeta = []
    pkg_to_layer = {}

    def get_pkg_name(pkg: MetaPackage):
        return f"meta:{pkg.name}" if pkg.meta else pkg.name

    for layer in dedi_layers:
        layer_name = f"dedi:{get_pkg_name(layer[0])}"

        smeta.append(
            {
                "identifier": layer_name,
                "name": layer_name,
                "srcid": layer_name,
                "change_time_offset": 1,
                "change_frequency": 1,
            }
        )
        for pkg in layer:
            pkg_to_layer[pkg.name] = layer_name

    for i, layer in enumerate(layers):
        layer_name = f"rechunk_layer{i}"
        layer_human = ",".join([get_pkg_name(pkg) for pkg in layer])

        unpackaged = len(layer) == 1 and layer[0].name == "unpackaged"
        smeta.append(
            {
                "identifier": layer_name,
                "name": layer_human,
                "srcid": f"rechunk_layer{i}",
                "change_time_offset": i,
                "change_frequency": 0xFFFFFFFF if unpackaged else 1,
            }
        )
        for pkg in layer:
            pkg_to_layer[pkg.name] = layer_name

    # Create mappings
    ostree_out = {}
    for fn, pkg in mapping.items():
        layer = pkg_to_layer[pkg]
        if fn in ostree_map:
            fhash = ostree_map[fn]
            ostree_hashes.pop(fhash, None)
            ostree_out[fhash] = layer

    for fhash in ostree_hashes:
        ostree_out[fhash] = layer_name

    with open(out_fn, "w") as f:
        json.dump(
            {
                "set": list(smeta),
                "map": ostree_out,
            },
            f,
            indent=2,
        )


if __name__ == "__main__":
    print(get_ostree_map("./tree.ls"))
