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

#
# /etc handling
#

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
    $TREE/.dockerenv \

# Merge /etc to /usr/etc
# OSTree will error out if both dirs exist
# And rpm-ostree will be confused and use only one of them
# /usr/etc might have broken permissions, so we sync /etc/ to it,
# even though /etc is much bigger
if [ -d $TREE/usr/etc ]; then
    rsync -a $TREE/etc/ $TREE/usr/etc
    rm -rf $TREE/etc
fi

#
# Other directories
#

# Copy opt

# # Copy var/lib to /usr/lib
# if [ -d $TREE/var ]; then
#     mkdir -p $TREE/usr/lib
#     rsync -a $TREE/var/lib/ $TREE/usr/lib/
#     rm -r $TREE/var/lib
# fi

# # Copy var files to factory
# if [ -d $TREE/var ]; then
#     mkdir -p $TREE/usr/share/factory/var
#     rsync -a $TREE/var/ $TREE/usr/share/factory/var/
# fi

# Remove top level dir contents
# TODO: fix /var/lib to symlink to /usr/lib
# const EXCLUDED_TOPLEVEL_PATHS: &[&str] = &["run", "tmp", "proc", "sys", "dev"];
echo
echo Removing top level directory contents:
find \
    $TREE/var/ \
    $TREE/run/ \
    $TREE/tmp/ \
    $TREE/proc/ \
    $TREE/sys/ \
    $TREE/dev/ \
    $TREE/boot/ \
    -mindepth 1 \
    -exec rm -rf {} + \
    -exec echo {} +
    # $TREE/etc/containers/* \ # Remove this ?

#
# Cache busters
#

# Changes every docker build
rm -rf $TREE/usr/lib/.build-id

# Make basic dirs
# that OSTree expects and will panic without
# (initramfs script will fail)
# https://github.com/M1cha/archlinux-ostree/

mkdir -p $TREE/sysroot
ln -s sysroot/ostree $TREE/ostree

# Containerfile overode RPM db, so now there are 2 RPM dbs
# Use hardlinks so analyzer cant take into account these being the same files
# rm -rf $TREE/usr/lib/sysimage/rpm-ostree-base-db/
# rsync -a \
#     --link-dest="../../../share/rpm" \
#     "$TREE/usr/share/rpm/" \
#     "$TREE/usr/lib/sysimage/rpm-ostree-base-db"

# Fix perms. Unsure why these break
# FIXME: Find out why and remove
chmod 750 $TREE/usr/etc/audit
chmod 750 $TREE/usr/etc/audit/rules.d
chmod 755 $TREE/usr/etc/bluetooth
chmod 750 $TREE/usr/etc/dhcp
chmod 750 $TREE/usr/etc/firewalld
chmod 700 $TREE/usr/etc/grub.d
chmod 700 $TREE/usr/etc/nftables
chmod 700 $TREE/usr/etc/nftables/osf
chmod 555 $TREE/usr/etc/pki/ca-trust/extracted/pem/directory-hash
chmod 750 $TREE/usr/etc/polkit-1/rules.d
chmod 700 $TREE/usr/etc/ssh/sshd_config.d
chmod 700 $TREE/usr/lib/containers/storage/overlay-images
chmod 700 $TREE/usr/lib/containers/storage/overlay-layers
chmod 700 $TREE/usr/lib/ostree-boot/efi
chmod 700 $TREE/usr/lib/ostree-boot/efi/EFI
chmod 700 $TREE/usr/lib/ostree-boot/efi/EFI/BOOT
chmod 700 $TREE/usr/lib/ostree-boot/efi/EFI/fedora
chmod 700 $TREE/usr/lib/ostree-boot/grub2
chmod 700 $TREE/usr/lib/ostree-boot/grub2/fonts
chmod 750 $TREE/usr/libexec/initscripts/legacy-actions/auditd

# Touch files for reproducibility
echo
echo Touching files with timestamp $TIMESTAMP for reproducibility
# Also remove user.overlay.impure, which comes from somewhere
sudo find $TREE/ \
    -exec touch -t $TIMESTAMP -h {} + \
    -exec setfattr --remove user.overlay.impure {} + \
    &> /dev/null || true
