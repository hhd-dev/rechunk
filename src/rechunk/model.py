from datetime import datetime
from typing import Literal, NamedTuple, Sequence, TypedDict


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


def export_v1(
    uniq: str | None,
    base_pkg: Sequence[Package] | None,
) -> str:
    import json

    packages = {}
    if base_pkg:
        for p in base_pkg:
            packages[p.name] = f"{p.version}-{p.release}"

    return json.dumps(ExportInfoV1(version=1, uniq=uniq or "", packages=packages))
