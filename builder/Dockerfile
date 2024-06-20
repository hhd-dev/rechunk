FROM quay.io/coreos-assembler/fcos-buildroot:testing-devel as build

#
# Usage dependencies
#
# Done before building rpm-ostree to allow adding more patches.

# Install niceties
RUN dnf install -y skopeo buildah just git jq fuse-overlayfs \
    make bubblewrap fedpkg selinux-policy-targeted

#
# Build ostree-rs-ext
#
# Required to unencapsulate OCI to ostree
# rpm-ostree seems to not have the ability.
# It is not provided as a package in fedora.
ARG OSTREE_EXT_TAG="ostree-ext-v0.14.1"
RUN mkdir -p /sources; \
    cd /sources; \
    git clone --branch ${OSTREE_EXT_TAG} --depth 1 \
    https://github.com/ostreedev/ostree-rs-ext ostree-rs-ext;

WORKDIR /sources/ostree-rs-ext

RUN cargo fetch
# Only run build after fetch to avoid
# re-downloading dependencies after fail
RUN cargo build --release
RUN cp /sources/ostree-rs-ext/target/release/ostree-ext-cli \
    /usr/bin/ostree-ext-cli

# Allow for user access to files through container
# and for use of sudo for escalation
ARG UID=1000
ARG GID=1000

RUN groupadd admin -g $GID && \
    useradd admin -u $UID -g admin -ms /bin/bash && \
    passwd -d admin && \
    echo "admin ALL=(root) NOPASSWD:ALL" > /etc/sudoers.d/user && \
    chmod 0440 /etc/sudoers.d/user

#
# Build rpm-ostree
#
# Is a package, but handling lib32 steam deps
# requires a couple patches. 
ARG RPM_OSTREE_TAG="v2024.6"
RUN mkdir -p /sources; \
    cd /sources; \
    git clone --branch ${RPM_OSTREE_TAG} --depth 1 \
    https://github.com/coreos/rpm-ostree rpm-ostree;

WORKDIR /sources/rpm-ostree

# Install dependencies
RUN git submodule update --init; \
    ./autogen.sh --prefix=/usr --libdir=/usr/lib64 --sysconfdir=/etc
RUN cargo fetch

# Make once to cache most of the build process
# TODO: Remove for production
RUN make

# Apply patches
COPY 0001-skip-multiple-packages-check-to-avoid-32bit-packages.patch /tmp/patch.patch
COPY 0001-place-all-etc-files-in-the-last-layer.patch /tmp/patch2.patch
RUN patch -Np1 < "/tmp/patch.patch"; \
    patch -Np1 < "/tmp/patch2.patch"

# Make with patches (90s vs 5m)
RUN make
RUN make install

#
# Post-build niceties
#
WORKDIR /workspace