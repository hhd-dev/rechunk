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


def get_layers(manifest):
    import json

    if not "Labels" in manifest:
        return None

    labels = manifest["Labels"]
    if not INFO_KEY in labels:
        return None

    try:
        info = json.loads(labels[INFO_KEY])
    except json.JSONDecodeError:
        return None

    if info["version"] < 2:
        return None
    
    if not "layers" in info:
        return None

    return info["layers"]


def export_v2(
    uniq: str | None,
    base_pkg: Sequence[Package] | None,
    layers: Sequence[Sequence[str]],
) -> str:
    import json

    packages = {}
    if base_pkg:
        for p in base_pkg:
            packages[p.name] = f"{p.version}-{p.release}"

    return json.dumps(
        ExportInfoV2(
            version=2,
            uniq=uniq or "",
            packages=packages,
            layers=layers,
        )
    )
