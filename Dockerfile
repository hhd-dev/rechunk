FROM quay.io/fedora/fedora:40 as build

#
# Build dependencies
#
RUN dnf install -y rust cargo libzstd-devel git openssl-devel \
    glib2-devel ghc-gio ostree-devel patch

#
# Build ostree-rs-ext
#
# Required to unencapsulate OCI to ostree
# rpm-ostree seems to not have the ability.
# It is not provided as a package in fedora.
ARG OSTREE_EXT_TAG="ostree-ext-v0.14.2"
RUN mkdir -p /sources; \
    cd /sources; \
    git clone --branch ${OSTREE_EXT_TAG} --depth 1 \
    https://github.com/ostreedev/ostree-rs-ext ostree-rs-ext;

WORKDIR /sources/ostree-rs-ext

RUN cargo fetch
RUN cargo build --release

# Apply patches
RUN mkdir -p /tmp/oext
COPY builder/ostree-ext/*.patch /tmp/oext
RUN for patch in /tmp/oext/*.patch; do \
    echo "Applying patch: $patch"; \
    patch -Np1 < $patch; \
    done

# Only run build after fetch to avoid
# re-downloading dependencies after fail
RUN cargo build --release

# Remove dependencies
FROM quay.io/fedora/fedora:40

# Install niceties
RUN dnf install -y python3 python3-pip python3-devel rsync \
    libzstd openssl glib2 ghc-gio ostree skopeo selinux-policy-targeted

# Copy the built binary after installing deps
COPY --from=build /sources/ostree-rs-ext/target/release/ostree-ext-cli \
    /usr/bin/ostree-ext-cli

# Install rechunk
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
RUN mkdir -p /sources/rechunk
COPY . /sources/rechunk/
RUN pip install --no-cache-dir /sources/rechunk/

#
# Post-build niceties
#
WORKDIR /workspace