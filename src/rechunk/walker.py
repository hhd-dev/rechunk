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
    inodes = set()

    for root, _, files in os.walk(directory):
        if "/sysroot/ostree" in root:
            continue
        if "/.build-id/" in root:
            continue

        for file in files:
            fn = os.path.join(root, file)
            if os.path.islink(fn):
                # Check soft links
                s = 0
            else:
                # Check hardlinks after softlink
                # so that follow_symlinks=True can be set
                # because the ./tree dir can be a symlink
                stat = os.stat(fn, follow_symlinks=True)
                st_size = stat.st_size
                st_ino = stat.st_ino
                if st_ino in inodes:
                    s = 0
                else:
                    s = st_size
                    inodes.add(st_ino)

            # remove leading dot
            print(f"{s} {fn[1:]}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        os.chdir(sys.argv[1])
        
    walk_files('.')