# Rechunk
**Rechunk** is a library for reprocessing an OSTree OCI image prior to distribution
(e.g., right after making it).
It flattens the file system tree, thereby removing files that were replaced in
later OCI layers, then re-partitions the image into a set of N equally sized
layers through a grouping algorithm.
These layers are then fed to `ostree-rs-ext`, which produces a new equivalent
OSTree commit that can be deployed or used as a base image.

It solves these four key issues:
  - Drops unused files and lowers image size
    - E.g., if you extend Kinoite and replace the kernel, you do not have to ship
        the old kernel which was part of the original OSTree commit.
  - Avoids layer changes
    - Package groups such as Plasma that update together get their own layers
      and through timestamp clamping have the same hashes.
      If KDE does not update, the user does not have to redownload it.
  - Improves download speed
    - Instead of downloading "OSTree Custom Layers", users download normal OSTree
      layers, which do not require re-commiting into OSTree through hashing.
  - Better update resuming
    - Packages are spread around N small layers instead of a couple big ones. When 
    resuming a download, only one of the small N layers gets thrown away.

And of course, when uploading a new image to registry, since a portion of layers
will already be there, uploads are faster.

> [!IMPORTANT]
> The action in this repository uses advanced podman features (e.g., mount) and 
> requires both root access (**not rootless** execution) and the **Ubuntu 24.04** 
> runner (not **latest** as of this writing).
> 
> It is recommended to build your image with buildah or podman using root (e.g.,
> `sudo podman build`) so that it can be mounted directly by this action
> and then removed for space savings.

## Results
Experimentally, we have seen that on Bazzite, due to extensive changes to Kinoite,
`rechunk` lowers the total image size by 1GB.
Then, if a user updates weekly, they get around a 40% reduction in download size (from 5GB to 3GB).
If they update every 1-2 days, they get a 60-80% reduction in download size (from 5GB to 1-1.5GB).
For images built back to back, the download size lowers by over 90% to 100MB-300MB,
which is the size of the RPM database (~110MB) and change.

### Time cost
`Rechunk` adds around 6-10 minutes of processing time 
to producing an OCI image.
Around 2 of those minutes are spent preparing the
image for committing, 3 minutes for `ostree` creating
the commit, and 4 minutes (can be lowered by skipping gzip compression)
for `ostree-rs-ext` to produce the final gziped oci directory.

`rechunk` itself takes around 20 seconds to 
load information from
`ostree` and 10 seconds to produce an analysis.

Most of this time is then recouped by skipping uploading
around half of the layers, which will already exist
in the registry (due to rechunking) and from the tester having to download a 
much smaller image.

## Compared to zstd:chunked
`rechunk` achieves this gain without using zstd:chunked, which is a feature that 
aims to achieve a similar goal through only downloading changed files.
This is good because zstd:chunked is not yet widely supported, and tools such as
rpm-ostree will probably never support the bandwidth sparing aspect of it.

Rechunk will also speed up downloading zstd:chunked images, by lowering the 
number of invalidated layers that have to be reprocessed every update.
In addition, when zstd-chunked becomes broadly available, we can do further 
optimizations on top of it, such as repositioning new files to the end of each 
layer, so that they can be downloaded with a smaller number of HTTP range requests.

Therefore, `rechunk` and zstd:chunked are complementary technologies.

## Algorithm
### 1: Preprocessing
`rechunk` works by first mounting an OCI image through `podman`.
Then, the OSTree repository that exists in the image is removed, and the image
is cleaned up (permissions wise and through file tweaks) to resemble a version 
that would be produced by `rpm-ostree compose` (see [1_prune.sh](./1_prune.sh);
having issues? PR changes).

### 2: Commiting
Then, the podman mount is commited into OSTree as a fresh commit, with OSTree
performing SELinux relabeling.
Afterwards, the OSTree repository files are touched to get a static timestamp
and avoid layer hashing changes.
Finally, the podman mount is removed, and if required for space savings,
the original image is removed as well.

### 3: Rechunk Preparation
The rechunk tool works on top of OSTree, with OSTree becoming the single source
of truth about which files exist in the image and their size (this is good
as we get to throw away the mount).

First, it builds a file map that maps from each file to its OSTree hash and size.
Then, it pulls the rpm database from OSTree and reads it with `rpm` to retrieve
the existing packages and their file mapping.

### 4: Rechunk Analysis
With the full file information, `rechunk` calculates the base package sizes.
Then, `rechunk` uses the concept of a "meta" package to group packages that update
together, together.
This is very simple, as it is trivial to group packages by their reported versions
and notice patterns by hand (you can see them in the provided 
[meta.yml](./src/rechunk/meta.yml)).

In addition, `rechunk` supports including arbitrary files in an OCI image as a meta
package as well.
This is useful, since as part of Bazzite we commonly include large compressed
files (e.g., the Steam bootstrap) that are not part of any package.
In the original OSTree implementation, those would be placed together in an
unpackaged layer and not cached, which is undesirable.

Finally, for packages that we do not have a meta package, we perform a heuristic
algorithm using their changelogs.
The last year of a package's changelogs are scanned and an array of 53 booleans
is formed, where each boolean represents whether the package was updated in
a certain week.
Then, in a four-step process we do the following:
  - Bundle small packages (less than 1 MB) in their own layer
  - Bundle medium packages (less than 5 MB) to their own layer
  - For each of the layers that were not dedicated to meta packages:
    - Grab the largest package that has not been bundled yet to form the layer seed
    - Until the layer reaches a predefined size (e.g., 40%/N of the total image size):
    - Add the package that causes that layer's total bandwidth cost over last year to rise the least
    - Complexity: N^2 where N is the package number
  - A few packages will remain. For the remaining packages:
    - Loop for each layer and each package and find the layer, package combo that increases yearly bandwidth cost the least
    - Repeat until all packages are placed
    - Complexity: M*N^2 (M is the layer number and N is the package number; very expensive, but N has been reduced considerably)

This process takes around 30 seconds and results in an OSTree hash to layer
mapping.

The following process is only performed in the first run. 
In following runs, rechunk begins with the previous image plan (which is bundled
into the previous image manifest) and only performs the last step.
Re-using the previous plan minimizes layer shifts, which lowers layer invalidation
and the subsequent download size.

### 5: Rechunking
Finally, this information is placed in a JSON file that is provided to a fork of
[`ostree-rs-ext`](https://github.com/hhd-dev/ostree-rs-ext) that has been modified 
to follow custom rechunking plans with a JSON file as input.
`ostree-rs-ext` was also modified to allow for custom labels, which apply
to both the Docker and OCI conventions, allowing them to be read both from
github and, e.g., skopeo, rpm-ostree.

### 6: Uploading
The end result is an OCI directory that can be pushed directly to a registry through 
skopeo (single threaded) or imported to podman (takes space and time) and then
uploaded (multi-threaded).
This image can also be zstd:chunked, in which case, the action in this repository
contains an environment variable for skipping `ostree-rs-ext`'s Gzip compression,
which lowers processing time by around 3 minutes.

## Differences between images
This action receives an OCI OSTree image (with custom layers) and produces a
mutated version. There might be drift between the two images, with one
of the images having issues the other one does not.
I.e., they should not be considered identical.

### Issues in the rechunked image
The OCI standard is not good at SELinux and permissions. To combat this,
`rpm-ostree` reuses directory permissions from the original commit when deploying
an image, which are lost during squashing.

This is important as after being touched in a container certain directories may relax their
permissions or change owner. 
For example, certain systemd directories can become accessible, which may cause 
systemd to fail to start, or the polkit directory might stop being owned by polkitd
(due to it missing from `/etc/group`), causing polkits to not work.

The file [./1_prune.sh](./1_prune.sh) attempts to manually mitigate the permissions issues.
Without this file, the image will not boot.
There are certainly other quirks that still need to be added to this file,
especially in regard to untested DEs such as Cosmic.

### Issues in the original image
However, this is not to say the original image is perfect.

Programs that were installed in the OCI container add entries to `/etc/passwd` and
`/etc/group`, which are not moved to `/usr/lib/passwd` and `/usr/lib/group` by 
`rpm-ostree`.
This works for clean installs, but if users rebase to a derived image, they
get user and group issues.

[./1_prune.sh](./1_prune.sh) performs a merge of these files to `/usr/lib/passwd`
and `/usr/lib/group` which means that images produced by this action do not
share these issues.

There are other little issues, such as `/var/lib`, additional lock files,
and modified `/var`, `/boot` directories, which may cause hysteresis in the final image
and are also handled by [./1_prune.sh](./1_prune.sh).

Furthermore, `rpm-ostree` uses the policy of the original commit when deploying an image,
causing new programs (e.g., Waydroid) to be labelled improperly when installed
through Docker and require workarounds.

As part of this action, OSTree performs relabelling using the full policy,
so the output image does not have the SELinux issues the original image had.

### TLDR
For quick testing and iteration locally, using the original image is fine.
However, before entering production, test, validate, and create workarounds
for issues in the rechunked image.