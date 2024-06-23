from typing import NamedTuple
from datetime import datetime


class File(NamedTuple):
    name: str
    size: int


class Package(NamedTuple):
    index: int
    name: str
    nevra: str
    size: int
    files: tuple[File, ...] = tuple()
    updates: tuple[datetime, ...] = tuple()
    dedicated: bool = False