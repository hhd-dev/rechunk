from typing import NamedTuple
from datetime import datetime


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