from datetime import datetime
from typing import Literal, NamedTuple, Sequence, TypedDict

INFO_KEY = "dev.hhd.rechunk.info"


class File(NamedTuple):
    name: str
    size: int


class Package(NamedTuple):
    name: str
    nevra: str
    size: int
    files: tuple[File, ...] = tuple()
    updates: tuple[datetime, ...] = tuple()
    version: str = ""
    release: str = ""


class MetaPackage(NamedTuple):
    index: int
    name: str
    nevra: tuple[str, ...]
    size: int
    updates: tuple[datetime, ...] = tuple()
    dedicated: bool = False
    meta: bool = False


class ExportInfoV1(TypedDict):
    version: Literal[1]

    uniq: str
    packages: dict[str, str]


class ExportInfoV2(TypedDict):
    version: Literal[2]

    uniq: str
    layers: Sequence[Sequence[str]]
    packages: dict[str, str]
    revision: str | None

def get_info(manifest):
    import json

    if not "Labels" in manifest:
        return None

    labels = manifest["Labels"]
    if not INFO_KEY in labels:
        return None

    try:
        return json.loads(labels[INFO_KEY])
    except json.JSONDecodeError:
        return None

ExportInfo = ExportInfoV1 | ExportInfoV2

def get_layers(info):
    if info["version"] < 2:
        return None
    
    if not "layers" in info:
        return None

    return info["layers"]


def export_v2(
    uniq: str | None,
    base_pkg: Sequence[Package] | None,
    layers: Sequence[Sequence[str]],
    revision: str | None = None,
) -> str:
    import json

    packages = {}
    if base_pkg:
        for p in base_pkg:
            # When we list the diff of packages, we list the first package
            # with a version. Here, the way this is done, the last is kept
            # So skip if one has been seen to match the logic.
            if p.name in packages:
                continue
            packages[p.name] = f"{p.version}-{p.release}"

    return json.dumps(
        ExportInfoV2(
            version=2,
            uniq=uniq or "",
            packages=packages,
            layers=layers,
            revision=revision,
        )
    )
