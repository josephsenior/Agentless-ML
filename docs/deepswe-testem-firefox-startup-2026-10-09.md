# Testem: separate Firefox image and offline startup

The separate image built successfully, and Firefox ESR 140.17.0 launched
headlessly offline, rendered a local page and executed its JavaScript. This is
a browser startup check, not a Testem public baseline or a readiness update.

Image tag: `agentless-ml/testem-firefox:2026-10-09`.
Image ID:

```
sha256:290cd40e1e05814859e3a0430b7bcbea77d92b8fcdd5161fd6ef1c1fc14e969d
```

The parent remains
`sha256:fce2e9ebe359b36b031e0b772159884795fc8383a047bc50eaa46c20fa06e4f6`.

## What the build changed

The builder rehashed the Firefox archive and all 71 package archives from the
[completed manifest](../experiments/deepswe/testem_no_upgrade_verified_2026_10_09.json)
before staging them. It copied only that explicit list, not the original audit's
whole download directory. The staged directory's wildcard therefore expands to
exactly those 71 archives, not the abandoned upgrades/service-package set.

The build used the existing digest-qualified parent, `--pull=false` and
`--network=none` for build steps. It unpacked/configured the verified local
packages with `dpkg`, checked the package database for incomplete configuration,
and confirmed the two preserved versions. The existing `policy-rc.d` denies
service startup; no new init/service manager was introduced. Firefox was extracted
under `/opt/firefox`, with an executable link at `/usr/local/bin/firefox`.
No Testem source, tests or node_modules were intentionally edited.

An offline inventory comparison of the parent and supplemented image proves
**exactly 71 new installed packages**, with versions matching the manifest, and
**no changed or removed existing installed package versions**. `libudev1` and
`libsystemd0` both remain `252.39-1~deb12u1`. This checks package inventory, not
every byte of every pre-existing file touched by ordinary package triggers.

Two unsuccessful build attempts were retained: the first used a bare image ID
which BuildKit misread as a registry name; it failed before installation. The
second resolved the correct pinned parent but APT rejected a local archive path.
Direct unpack/configure of the same verified set fixed that build plumbing.
No package pin, dependency constraint or runtime protection was relaxed. BuildKit
attempted registry metadata resolution during the first failure; the offline
build-step setting is not a claim that BuildKit can never contact a registry.

## Offline browser check

The browser used a fresh profile, home, cache and config paths under `/tmp`.
It rendered a local HTML file; neither a remote page nor a benchmark fixture
was involved. The check returned zero, reported the expected version and
produced a **640-by-480 PNG, 25,756 bytes**. Visual inspection confirmed both
the heading and the JavaScript-updated text.

Screenshot SHA-256:

```
c29a9e597945167289355efbb735af97ee8697b3b4c612a721d6515c4e3de5ab
```

Docker inspection confirms unchanged execution protections:

- No network and a read-only root filesystem.
- All capabilities dropped, no-new-privileges and no privileged mode.
- 8-GiB memory with no extra swap allowance, two CPUs, 2,048 PIDs.
- The same 4-GiB executable, nosuid/nodev `/tmp` mount.

Firefox emitted `CanCreateUserNamespace() clone() failure: EPERM`, plus graphics
probe warnings about missing `libpci`, `libGL.so.1` and no detected GPUs. These
did not prevent this headless rendering check. We did not add libraries in
response, disable Firefox's sandbox or change Docker seccomp/capabilities.
This establishes that the requested Docker boundaries were retained, **not**
that every Firefox internal sandbox mechanism was active. We have not audited
its internal fallback behavior or demonstrated GPU/media support.

The first browser invocation also rendered successfully, but the host tried to
copy the screenshot after the exited container's tmpfs was unavailable. That
artifact-export error is retained separately. The corrected helper exports the
PNG through the command response before exit, verifies its hash and size, and
then saves it. One further startup invocation passed with the same PNG hash.
Both owned containers were removed. No public test was run in either invocation.

## Next step

Run the unchanged full public Testem schedule against this exact labelled image,
with the normal resource protections and the published 1,800-second cap. That
will check real launch/cleanup behavior and test reporting; rendering one page
does not prove the suite finishes. It has not been started. Canonical readiness
remains **100/113** and the original-image timeout record is unchanged.

Raw evidence is in `../output/deepswe-survey/testem-firefox/`: `build.json`,
`inventory.json`, `startup.json`, `startup.png`, build/startup logs, the two failed
build logs and the first startup capture-error record. The compact committed
[result](../experiments/deepswe/testem_firefox_startup_2026_10_09.json) keeps the
image identity and recorded Docker protections. No held-out tests or solutions
were read. KGateway remains parked.
