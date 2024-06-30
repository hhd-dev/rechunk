#!/usr/bin/env bash
# Prune files in tree that are extraneous

if [ $(id -u) -ne 0 ]; then
    echo "Run as superuser"
    exit 1
fi

if [ -z "$TREE" ]; then
    echo "TREE is empty. Please be careful! This script can prune your system!"
    exit 1
fi

TREE=${TREE:=./tree}
pushd $TREE

TIMESTAMP=${TIMESTAMP:=197001010100}

# Copy _everything_ including perms
RSYNC="rsync -aAX"

# # Prevent heavy tears by forcing relative path
# TREE=./$TREE

# Main OSTree dir, is remade in the end
# If it contains kinoite files that were removed by bazzite,
# they will be retained, bloating the final image
echo Pruning files in $TREE
rm -rf ./sysroot
rm -rf ./ostree

#
# /etc handling
#

# Handle files that rpm-ostree would normally remove
if [ -f ./etc/passwd ]; then
    echo
    echo Appending the following passwd users to /usr/lib/passwd
    out=$(grep -v "root" ./etc/passwd)
    echo "$out"
    echo "$out" >> ./usr/lib/passwd
fi
if [ -f ./etc/group ]; then
    echo
    echo Appending the following group entries to /usr/lib/group
    out=$(grep -v "root\|wheel" ./etc/group)
    echo "$out"
    echo "$out" >> ./usr/lib/group
fi

if [ -f ./etc/passwd ] || [ -f ./etc/group ]; then
    echo
    echo "Warning: Make sure processed users and groups are from installed programs!"
fi

# Create defaults for /etc/passwd, /etc/group
cat <<EOT > ./etc/passwd
root:x:0:0:root:/root:/bin/bash
EOT
cat <<EOT > ./etc/group
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
    ./etc/.pwd.lock \
    ./etc/passwd- \
    ./etc/group- \
    ./etc/shadow- \
    ./etc/gshadow- \
    ./etc/subuid- \
    ./etc/subgid- \
    ./.dockerenv

# Merge /usr/etc to /etc
# OSTree will error out if both dirs exist
# And rpm-ostree will be confused and use only one of them
if [ -d ./usr/etc ]; then
    # # Fix dir perms
    # # These may prevent the system from booting
    # # Systemd expects certain dirs to be readable only by root
    # echo Fixing /usr/etc dir perms
    # pushd ./usr/etc
    # find . -type d -exec chown -v --reference='{}' ../../etc/'{}' \; | grep changed
    # find . -type d -exec chmod -v --reference='{}' ../../etc/'{}' \; | grep changed
    # popd
    # Sync
    echo Merging /usr/etc to /etc
    $RSYNC ./usr/etc/ ./etc
    rm -rf ./usr/etc
fi

# Move /etc to /usr/etc
mv ./etc ./usr/

#
# Other directories
#

# Copy opt

# Copy var/lib to /usr/lib
if [ -d ./var ]; then
    mkdir -p ./usr/lib
    $RSYNC ./var/lib/ ./usr/lib/
    rm -r ./var/lib
fi

# Copy var files to factory
if [ -d ./var ]; then
    mkdir -p ./usr/share/factory/var
    $RSYNC ./var/ ./usr/share/factory/var/
fi

# Remove top level dir contents
# TODO: fix /var/lib to symlink to /usr/lib
# const EXCLUDED_TOPLEVEL_PATHS: &[&str] = &["run", "tmp", "proc", "sys", "dev"];
echo
echo Removing top level directory contents:
find \
    ./var/ \
    ./run/ \
    ./tmp/ \
    ./proc/ \
    ./sys/ \
    ./dev/ \
    ./boot/ \
    -mindepth 1 \
    -exec rm -rf {} + \
    -exec echo {} +
    # ./etc/containers/* \ # Remove this ?

#
# Cache busters
#

# Changes every docker build
rm -rf ./usr/lib/.build-id

# Make basic dirs
# that OSTree expects and will panic without
# (initramfs script will fail)
# https://github.com/M1cha/archlinux-ostree/

mkdir -p ./sysroot
ln -s sysroot/ostree ./ostree

# Containerfile overode RPM db, so now there are 2 RPM dbs
# Use hardlinks so analyzer cant take into account these being the same files
rm -rf ./usr/lib/sysimage/rpm-ostree-base-db/
$RSYNC \
    --link-dest="../../../share/rpm" \
    "./usr/share/rpm/" \
    "./usr/lib/sysimage/rpm-ostree-base-db"

# Fix perms. Unsure why these break
# FIXME: Find out why and remove
chmod 750 ./usr/etc/audit
chmod 750 ./usr/etc/audit/rules.d
chmod 755 ./usr/etc/bluetooth
chmod 750 ./usr/etc/dhcp
chmod 750 ./usr/etc/firewalld
chmod 700 ./usr/etc/grub.d
chmod 700 ./usr/etc/nftables
chmod 700 ./usr/etc/nftables/osf
chmod 555 ./usr/etc/pki/ca-trust/extracted/pem/directory-hash
chmod 750 ./usr/etc/polkit-1/rules.d
chmod 700 ./usr/etc/ssh/sshd_config.d
chmod 700 ./usr/lib/containers/storage/overlay-images
chmod 700 ./usr/lib/containers/storage/overlay-layers
chmod 700 ./usr/lib/ostree-boot/efi
chmod 700 ./usr/lib/ostree-boot/efi/EFI
chmod 700 ./usr/lib/ostree-boot/efi/EFI/BOOT
chmod 700 ./usr/lib/ostree-boot/efi/EFI/fedora
chmod 700 ./usr/lib/ostree-boot/grub2
chmod 700 ./usr/lib/ostree-boot/grub2/fonts
chmod 750 ./usr/libexec/initscripts/legacy-actions/auditd

# Fix polkid group
POLKIT_ID=$(cat ./usr/lib/group | grep polkitd | cut -d: -f3)
if [ -z "$POLKIT_ID" ]; then
    echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
    echo "Polkitd group not found. Polkits will not work"
    echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
else
    echo "Fixing polkit perms"
    chgrp $POLKIT_ID ./usr/etc/polkit-1/localauthority
    chgrp $POLKIT_ID ./usr/etc/polkit-1/rules.d
fi

# Touch files for reproducibility
echo
echo Touching files with timestamp $TIMESTAMP for reproducibility
# Also remove user.overlay.impure, which comes from somewhere
sudo find ./ \
    -exec touch -t $TIMESTAMP -h {} + \
    -exec setfattr -h --remove user.overlay.impure {} + \
    &> /dev/null || true

# popd