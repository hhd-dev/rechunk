#!/usr/bin/env bash
# Prune files in tree that are extraneous

if [ $(id -u) -ne 0 ]; then
    echo "Run as superuser"
    exit 1
fi

TREE=${TREE:=./tree}
TIMESTAMP=${TIMESTAMP:=202001010100}

# Prevent heavy tears by forcing relative path
TREE=./$TREE

# Main OSTree dir, is remade in the end
# If it contains kinoite files that were removed by bazzite,
# they will be retained, bloating the final image
echo Pruning files in $TREE
rm -rf $TREE/sysroot
rm -rf $TREE/ostree

# Handle files that rpm-ostree would normally remove
if [ -f $TREE/etc/passwd ]; then
    echo
    echo Appending the following passwd users to /usr/lib/passwd
    out=$(grep -v "root" $TREE/etc/passwd)
    echo "$out"
    echo "$out" >> $TREE/usr/lib/passwd
fi
if [ -f $TREE/etc/group ]; then
    echo
    echo Appending the following group entries to /usr/lib/group
    out=$(grep -v "root\|wheel" $TREE/etc/group)
    echo "$out"
    echo "$out" >> $TREE/usr/lib/group
fi

if [ -f $TREE/etc/passwd ] || [ -f $TREE/etc/group ]; then
    echo
    echo "Warning: Make sure processed users and groups are from installed programs!"
fi

# Remove passwd and group backup files
rm -rf $TREE/etc/passwd- \
    $TREE/etc/group- 

# Create defaults for /etc/passwd, /etc/group
cat <<EOT > $TREE/etc/passwd
root:x:0:0:root:/root:/bin/bash
EOT
cat <<EOT > $TREE/etc/group
root:x:0:
wheel:x:10:
EOT

# Extra lock files created by container processes that might cause issues
# Referencing OSTree
# // Lock/backup files that should not be in the base commit (TODO fix).
# static PWGRP_LOCK_AND_BACKUP_FILES: &[&str] = &[
#     ".pwd.lock",
#     "passwd-",
#     "group-",
#     "shadow-",
#     "gshadow-",
#     "subuid-",
#     "subgid-",
# ];
rm -rf \
    $TREE/etc/.pwd.lock \
    $TREE/etc/passwd- \
    $TREE/etc/group- \
    $TREE/etc/shadow- \
    $TREE/etc/gshadow- \
    $TREE/etc/subuid- \
    $TREE/etc/subgid- \

# Merge /usr/etc to /etc then copy it back
# OSTree will error out if both dirs exist
# And rpm-ostree will be confused and use only one of them
rsync -a $TREE/usr/etc/ $TREE/etc/
rm -rf $TREE/usr/etc
mv $TREE/etc $TREE/usr/etc 

# Extra files leftover from container stuff
rm -rf \
    $TREE/run/* \
    $TREE/var/* \
    $TREE/boot/* \
    .dockerenv \
    $TREE/etc/containers/* \

# Make basic dirs
# that OSTree expects and will panic without
# (initramfs script will fail)
# https://github.com/M1cha/archlinux-ostree/

mkdir -p $TREE/sysroot
ln -s sysroot/ostree $TREE/ostree

# Deal with /boot?

# Touch files for reproducibility
echo
echo Touching files with timestamp $TIMESTAMP for reproducibility
# Also remove user.overlay.impure, which comes from somewhere
sudo find $TREE/ \
    -exec touch -t $TIMESTAMP -h {} + \
    &> /dev/null
# This attribute exists in some files, could be removed
# but seems harmless and causes a delay
# -exec setfattr --remove user.overlay.impure {} + \
