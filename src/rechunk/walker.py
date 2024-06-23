#!/usr/bin/env python

# This script is a python version of the following shell command:
#
# find / \
#   -not -path '/sysroot/ostree/*' \
#   -not -path '*/.build-id/*' \
#   -exec stat -c%n\\ %y {} \\;
#
# The reason the bash command cannot be used is that it forks to call
# the command stat for each file. There are more than 200k files.
# The find command just for the filenames returns in 2s, for stat it does not.
#
# This script runs in a modest 10s.

import os


def walk_files(directory):
    for root, _, files in os.walk(directory):
        if "/sysroot/ostree" in root:
            continue
        if "/.build-id/" in root:
            continue

        for file in files:
            fn = os.path.join(root, file)
            if os.path.islink(fn):
                s = 0
            else:
                s = os.path.getsize(fn)

            # remove leading dot
            print(f"{s} {fn[1:]}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        os.chdir(sys.argv[1])
        
    walk_files('.')