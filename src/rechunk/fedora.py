import logging
from datetime import datetime
from typing import Literal

from .model import File, Package
from .utils import run, run_nested

logger = logging.getLogger(__name__)


def get_packages(dir: str):
    packages = []

    fail_count = 0
    i = 0
    files = []
    updates = []
    mode: Literal["changelog", "file"] = "changelog"

    for line in run_nested(
        'rpm -qa --queryformat ">\n[%{FILESIZES} %{FILENAMES}\n]<%{NAME} %{NEVRA} %{SIZE}\n" --changes',
        dir,
    ).splitlines():
        if line.startswith("<"):
            data = line[1:].split(" ")
            name = data[0]
            nevra = data[1]
            size = int(data[2])
            package = Package(name, nevra, size, tuple(files), tuple(updates))
            packages.append(package)

            files = []
            updates = []
            i += 1
            mode = "changelog"
        elif line.startswith(">"):
            mode = "file"
        else:
            if mode == "changelog" and line.startswith("* "):
                try:
                    updates.append(
                        datetime.strptime(line[2:26], "%a %b %d %H:%M:%S %Y")
                    )
                except ValueError:
                    # There are 2 dates without time we could parse
                    # but lets keep the code simple
                    fail_count += 1

            elif mode == "file":
                size = int(line[: line.index(" ")])
                name = line[line.index(" ") + 1 :]
                files.append(File(name, size))

    if fail_count:
        logger.warning(f"Failed to parse {fail_count} changelog entries")

    return packages
