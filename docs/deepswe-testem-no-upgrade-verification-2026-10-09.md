# Testem: the revised dependency set passes static checks

The remaining `dbus-x11` archive is verified, and the revised **71-package,
zero-upgrade set** has no missing shared-library names in the offline ELF check.
No supplemented image has been built and no browser or tests have run.

## The new archive

We downloaded only the new Debian archive:

```
dbus-x11_1.14.10-1~deb12u1_amd64.deb
```

Its size is **91,004 bytes** and SHA-256 is:

```
42335faa76412a5ba1f173ba26a99863428e4915751114862edc70e4a09f9b0b
```

The archive came from the exact official Debian pool URL recorded in the
[completed manifest](../experiments/deepswe/testem_no_upgrade_verified_2026_10_09.json).
The hash and size match its record in the previously authenticated, frozen
Bookworm package index. We rehashed the saved metadata against the original
audit pins, repeated offline `gpgv` verification of all three `InRelease`
signatures, and rechecked the package record. We did not refresh the package
lists or accept a new moving version. The `.deb` control fields also match the
expected package, version and amd64 architecture.

All 70 reused archives were rehashed and size-checked too, as was the pinned
Firefox archive against its previously authenticated SHA-512. The historical
87-package audit and the earlier pending candidate manifest remain unchanged.
The new completed manifest records all 71 archives as verified.

## Revised coverage, not the old directory wildcard

The offline inspector extracted only the manifest's explicit 71 selected
archives into `/tmp/native-root`. It did not extract the other packages still
present in the acquisition directory. In particular it did not overlay
`libudev1`, `libsystemd0`, systemd, systemd-sysv or libpam-systemd.

It inspected **143 regular ELF files** using `readelf -d`: 27 from Firefox and
116 from the selected native payloads. For each `DT_NEEDED` name it recorded
a provider in the original image's library cache, Firefox's bundled libraries
or a selected payload's ELF SONAME/basename. No required name was missing,
including the transitive dependencies of the inspected native binaries and
libraries. This is stronger than inspecting only Firefox's direct imports,
but is still static library-name coverage, not dynamic loading or symbol-version
compatibility verification. Runtime search paths, modules loaded by `dlopen`,
generated package data, profiles and browser sandbox behavior remain untested.

The provider record specifically shows:

- `libdbus-1`, dbus-daemon and dbus-run-session use the image's existing
  `libsystemd.so.0`.
- The selected colord libraries use the image's existing `libudev.so.1`.
- Both installed package versions remain **252.39-1~deb12u1**.

The image package database hash matches the one recorded during the upgrade
review. Extracting payloads ran no maintainer scripts and installed no package.
The 71 package archives total **34,294,952 bytes**; this is compressed archive
size, not final image size or scratch use during a future baseline.

## Boundary and next step

Only acquisition of the new archive used external HTTPS. All signature,
package-identity and ELF checks ran in offline disposable containers with the
same resource limits, read-only root and Docker protections. No tests, assertions,
public schedule, parent image or official survey records were changed. Canonical
readiness remains **100/113**, and KGateway stays parked.

Next: build a separate labelled image from this **completed explicit manifest**,
preserving the two original library versions and avoiding the old directory
wildcard. Then check actual headless Firefox startup offline with a writable
`/tmp` profile/home and unchanged Docker/sandbox protections before considering
the unchanged full public test schedule. None of those next actions has started.

Raw evidence is under
`../output/deepswe-survey/testem-firefox-audit-2026-10-09/`:
`no-upgrade-verification.json`, `no-upgrade-elf-coverage.json`,
`no-upgrade-selection.json`, and `no-upgrade-debian-signatures.json`.

Follow-up: the [approved separate image](deepswe-testem-firefox-startup-2026-10-09.md)
built and passed offline headless page rendering. Inventory confirms the exact
71 additions and no existing package-version changes. The public schedule
remains unrun in this supplemented environment.
