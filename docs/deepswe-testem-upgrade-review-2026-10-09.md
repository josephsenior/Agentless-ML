# Testem: keep the existing system libraries

The two proposed upgrades are avoidable. An offline APT simulation accepts
the same Firefox-support library requests while preserving the image's existing
`libudev1` and `libsystemd0` versions. The resulting plan has **71 new packages,
zero upgrades and zero removals**, instead of 85 new packages and two upgrades.

I recommend this smaller plan for the separately labelled browser image. It is
not a claim of minimality, runtime compatibility or equivalent security between
old and new system library versions. No image has been built.

## Why the original solver chose the upgrades

Both installed libraries are `252.39-1~deb12u1`; the acquired candidates are
`252.39-1~deb12u2`, from the same Debian Bookworm systemd source package.

The original package plan follows this dependency chain:

```
GTK common data -> dconf backend -> dconf service -> session-bus provider
                                                      |
                                                dbus-user-session
                                                      |
                                              systemd + PAM integration
```

The chosen systemd package requires exactly matching `libsystemd0` and
`libsystemd-shared` versions. This introduces systemd/PAM/session packages and
the `libsystemd0` upgrade; the original solver also chooses the newer `libudev1`.
But GTK's `libcolord2` dependency only requires `libudev1 >= 196`, and the DBus
library requires `libsystemd0` without an exact new version. Those library-level
requirements do not themselves demand the proposed upgrades.

The authenticated package records show an alternative: `dconf-service` accepts
`default-dbus-session-bus | dbus-session-bus`, and Debian's
[`dbus-x11`](https://packages.debian.org/bookworm/dbus-x11) supplies a session-bus
provider without depending on systemd/PAM integration. It still brings real
DBus utilities and a daemon; it is not a dummy dependency or simulated service.
Selecting this provider does not require launching a desktop session or X server
for the planned headless Firefox check. Actual browser operation remains untested.

## What the offline simulations established

We reused the signed package lists and pinned image from the
[dependency audit](deepswe-testem-firefox-verification-2026-10-09.md). All three
simulations returned zero:

1. Original requests: 85 new packages, two upgrades.
2. Original requests plus both existing library versions explicitly pinned:
   71 new packages, zero upgrades. APT chooses `dbus-x11` itself.
3. The preserved-version requests plus explicit `dbus-x11`: the same 71-package,
   zero-upgrade plan. This is the recommended explicit future recipe.

All simulations retain `--no-install-recommends` and the same top-level requests:
`libgtk-3-0`, `libasound2`, `libdbus-glib-1-2`, `libx11-xcb1`, `libxt6`.
There is no forced dependency break, ignored package requirement or suite change.

The revised plan omits 17 entries from the original install/upgrade set and adds
`dbus-x11` version `1.14.10-1~deb12u1`. Omissions include the two upgrades,
systemd, systemd-sysv, libpam-systemd, dbus-user-session and the extra block-device
and cryptsetup chain. They are not removals from the parent image. The existing
libraries stay installed and unchanged.

Seventy selected archives were already downloaded and verified in the first
audit, with exactly matching versions. `dbus-x11` is the one new artifact:
its exact version, size and SHA-256 were read from the authenticated package
index, but its bytes **have not been downloaded or checksum-verified** yet.
The [reviewed candidate manifest](../experiments/deepswe/testem_no_upgrade_candidate_2026_10_09.json)
marks this distinction explicitly. The original 87-package verification manifest
is preserved as historical evidence, not overwritten into the new plan.

## What the upgrades would change

We rehashed the two acquired `.deb` files and inspected their payloads and
maintainer-script control data without running them. They contain runtime shared
libraries; their only extracted maintenance hook is an `ldconfig` trigger.
Installing either library alone is not the same thing as installing/running
systemd as PID 1. The broader service additions came from the original dependency
resolution, not these two library packages secretly starting services.

Their shared source changelog includes security fixes in the `deb12u2` revision.
Preserving the base versions is a controlled benchmark-environment choice, not
a declaration that those updates are unnecessary for general system maintenance
or that the parent image is fully patched. We did not perform a vulnerability
or complete binary-ABI audit. No browser-specific need for the two upgrades was
established, and the no-upgrade simulation is sufficient reason to avoid changing
them for this diagnostic condition.

## Next step and boundary

Verify the single new `dbus-x11` archive against its pinned index hash, then
repeat static dependency coverage using only the revised selected payloads and
the original image libraries. Only afterwards consider the separate image build
and browser startup check. Do not install the entire old 87-package directory
by wildcard: it includes precisely the upgrades and service packages avoided here.

All review containers ran offline, read-only, with the existing resource caps
and Docker protections. No package was installed, dependency downloaded, image
built or tests run. Canonical readiness remains **100/113**; KGateway stays parked.
Raw simulations, installed versions, payload/script inspection and changelog
excerpts are in
`../output/deepswe-survey/testem-firefox-audit-2026-10-09/upgrade-review.json`.

Follow-up: the [approved archive and coverage check](deepswe-testem-no-upgrade-verification-2026-10-09.md)
has now verified `dbus-x11` and all 71 selected archives. Static inspection of
143 ELF files found no missing library names, with the original system libraries
preserved. No image or runtime test has been started.
