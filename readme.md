# Bazzite Update Utilities
This project implements some niceties around rpm-ostree and Steam, so that it
is more convenient for users of Bazzite to manage updates for their system.

Specifically, it allows repackaging an existing OCI image into a chunked base
image and drops duplicate files, through using `rpm-ostree container encapsulate`.
Then, by using skopeo and receiving the output of rpm-ostree, it outputs
the current update progress.