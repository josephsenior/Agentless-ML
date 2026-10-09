# Testem: verified Firefox and native-library candidate

The pre-build audit passed. We acquired and verified **Firefox ESR 140.17.0,
Linux x86-64, en-US**, plus **87 Debian Bookworm packages**. Static inspection
found 21 shared-library names missing from the original image; the downloaded
package payloads cover all 21. No browser was executed, package installed,
supplemented image built or public test run.

This is an explicit candidate pin, not a reconstruction of Testem's historical
browser resolution. Its public CI installs Firefox without pinning a version.
Mozilla's product metadata listed `140.17.0esr` as the ESR release at audit time;
we froze that exact archive rather than retaining a moving download URL.

## Browser authenticity

Archive source:
[Mozilla's official release archive](https://archive.mozilla.org/pub/firefox/releases/140.17.0esr/linux-x86_64/en-US/).
Archive size: **75,743,336 bytes**. Its SHA-256 is:

```
86d049070ad80b74d8e674793e22d28923b4a7a1da06b4d65402f91c67a10314
```

We verified Mozilla's detached signature on `SHA512SUMS`, matched the exact
archive path once, and checked the downloaded archive against that signed
SHA-512 entry. The full SHA-512 is retained in the
[manifest](../experiments/deepswe/testem_firefox_dependencies_2026_10_09.json).

The primary fingerprint is
`14F26682D0916CDD81E37B6D61B7B526D98F0353`; the validated signing subkey is
`827E658608679618CD349F93678E455D76767AA3`. Both were independently pinned from
[Mozilla's August 2026 key-rotation notice](https://blog.mozilla.org/security/2026/08/10/updated-gpg-key-for-signing-firefox-and-thunderbird-releases/),
not accepted merely because a downloaded key could verify its own manifest.
GnuPG reported a valid signature by that subkey. Its unknown local trust warning
is expected for a temporary keyring; the explicit fingerprint check establishes
the intended identity. Old expired subkeys listed in the key bundle were not
used to accept this signature.

## Native dependency audit

The pinned Testem image is Debian 12 Bookworm, x86-64, with glibc 2.36. Mozilla's
[Firefox 140 requirements](https://www.firefox.com/en-US/firefox/140.0/system-requirements/)
call for GTK, GLib and other runtime libraries that the original image lacks.
We used `readelf -d`, not `ldd` or execution of downloaded Firefox binaries, to
inspect all ELF files in the verified archive.

An acquisition-only container fetched official Debian Bookworm, Bookworm Updates
and Bookworm Security metadata over HTTPS. APT validated the signed metadata
with the pinned image's Debian archive keyring, simulated dependency resolution,
and downloaded packages without installing them. Every `.deb` was checked for
exact version, architecture, size and SHA-256 against its authenticated package
record. We then verified all three `InRelease` signatures again offline using
`gpgv`. The pinned image's archive-keyring SHA-256 was:

```
506b815cbb32d9b6066b4a2aa524071e071761e7e7f68c3ac74f3061ba852017
```

The 87 downloaded archives total **40,680,832 bytes**. Main package pins include:

- `libgtk-3-0` **3.24.38-2~deb12u3**.
- `libglib2.0-0` **2.74.6-2+deb12u9**.
- `libasound2` **1.2.8-1+b1**.
- `libdbus-glib-1-2` **0.112-3**.
- `libx11-xcb1` **2:1.8.4-2+deb12u2**.
- `libxt6` **1:1.2.1-1.1**.

The manifest records all transitive package versions, hashes, sizes, repository
filenames and dependency declarations, not just these top-level packages.

APT's proposed installation is **85 new packages plus two upgrades**:
`libudev1` and `libsystemd0`, from `252.39-1~deb12u1` to `252.39-1~deb12u2`.
It also brings in systemd/DBus-related packages through its normal dependency
choices. These are disclosed environment changes, not an approved minimal build
recipe. Downloading them did not install services or change the parent image.
APT emitted read-only cache/lock warnings; its download-only command succeeded,
and neither the image's package database nor root filesystem was made writable.

For the final offline check, we extracted `.deb` payloads into a temporary
directory with `dpkg-deb -x`, without executing maintainer scripts. All Firefox
`DT_NEEDED` names then had a provider in the browser, the original image's
library cache or these payloads. This is a static name-coverage result, not
dynamic linker execution, complete ABI validation or proof about every `dlopen`
path. The package solver establishes Debian package-level dependencies; that
does not establish Firefox's full runtime behavior.

## Boundary and next step

Only the acquisition container had networking, solely for official package
metadata and archives. Signature and ELF checks ran offline. All inspectors
kept the same resource caps, read-only root, dropped capabilities and
no-new-privileges, and were automatically removed. No candidate tests, held-out
corpus tests or solutions were read as part of this dependency audit.

Next, assess how to stage these verified payloads in a separate labelled image,
explicitly accounting for the two proposed upgrades and service-package payloads.
Build only with approval. Then check browser launch with writable `/tmp` profile
and home paths, offline, under unchanged sandbox protections; do not preemptively
disable Firefox's sandbox, use privileged Docker or mount the host broadly.
Only after that should an unchanged full public schedule be considered.

Raw downloaded artifacts, signatures, APT logs and before/after ELF results are
outside Git at `../output/deepswe-survey/testem-firefox-audit-2026-10-09/`.
The committed manifest pins the artifacts; it does not bundle executables.
Canonical readiness remains **100/113**, and no retry was started.

Follow-up: the [upgrade review](deepswe-testem-upgrade-review-2026-10-09.md)
identified a valid no-upgrade 71-package alternative. Keep this original
87-package audit as evidence, not as the recommended future install list.
