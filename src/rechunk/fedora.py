import logging
import subprocess
from datetime import datetime
from typing import Literal

from .model import File, Package

logger = logging.getLogger(__name__)


def get_packages(dir: str):
    packages = []

    fail_count = 0
    i = 0
    files = []
    updates = []
    mode: Literal["changelog", "file"] = "changelog"

    for eline in subprocess.run(
        [
            "rpm",
            "-qa",
            "--queryformat",
            '>\n[%{FILESIZES} %{FILENAMES}\n]<%{NAME} %{NEVRA} %{SIZE}\n',
            "--changes",
            "--dbpath",
            dir,
        ],
        stdout=subprocess.PIPE,
    ).stdout.splitlines():
        line = eline.decode("utf-8")

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
                date = None
                for format in ["%a %d %b %Y %H:%M:%S", "%a %b %d %H:%M:%S %Y"]:
                    try:
                        date = datetime.strptime(line[2:26], format)
                        break
                    except ValueError:
                        pass
                if date:
                    updates.append(date)
                else:
                    fail_count += 1

            elif mode == "file":
                size = int(line[: line.index(" ")])
                name = line[line.index(" ") + 1 :]
                files.append(File(name, size))
    if fail_count:
        logger.warning(f"Failed to parse {fail_count} changelog entries")

    return packages
