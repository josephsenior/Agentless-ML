# Writable NodeBB dependencies: assessment

The connected baseline stopped because npm tried to rename
`node_modules/.bin/acorn`, while `.bin` was a link into the read-only image.
The public plugin test legitimately installs, upgrades and removes a package.
That requires a mutable dependency workspace; opening the network alone
cannot provide it.

## Recommended layout

Use a **full private copy of `/app/node_modules` under `/tmp/work/node_modules`**
for this connected, unpatched-base diagnostic. Keep `/app` and the container
root read-only. Preserve executable modes, relative links and the hidden npm
lockfile; let the copy belong to the container's running user rather than
trying to restore image UID/GID ownership. The assessed copy operation is
`cp -a --no-preserve=ownership` into a new destination.

Do not change the shared dependency-linking helper used by other repositories.
Do not follow it with a copy into an already linked directory: construct the
private NodeBB tree instead of the links in a separately labelled setup.
Continue to generate the root `package.json` from the pinned candidate's
`install/package.json`. Do not silently substitute the image's root manifest
or lockfile for candidate metadata.

Copying only `.bin` would fix the observed rename, but is not a sound general
boundary. The installed npm 10.8.2 Arborist implementation retires both package
paths and their executable paths during reconciliation (`reify.js`,
`_addNodeToTrashList`). Other package paths can therefore need writes too.
A full copy avoids borrowing immutable package directories through links.
No overlay privilege, writable image root, host mount or additional capability
is needed.

## What was verified on 14 October 2026

The original pinned image contains 45,745 regular dependency files and 88 links.
All link targets resolve inside the dependency tree. There are three native
`.node` files and a version-3 hidden lockfile with 1,394 package entries.
The native files are existing dependencies, not copies of candidate-generated
source or replacements for a candidate build.

An offline container copied the complete tree into disposable RAM-backed
scratch under the existing one-CPU, 4-GiB memory and 4-GiB scratch ceilings.
It retained dropped capabilities and no-new-privileges. Its PID ceiling was
128, stricter than the full baseline's 2,048. No ports or host paths were exposed.

The diagnostic compared content, regular-file modes and link targets across
the image and copy. It then renamed and restored `.bin/acorn` and
`acorn/package.json`, and created and removed a temporary file inside the
copied package. Every check passed. The original dependency tree and restored
copy still had the same inventory digest. The copy includes the hidden lock.

The copy held 534,971,324 regular-file bytes; scratch allocation was 640,144 KiB
(about 625 MiB). Cgroup peak memory was 884,748,288 bytes (about 844 MiB).
The diagnostic took 6.79 seconds. These measurements exclude NodeBB asset
compilation, Redis, npm installation and test execution: they establish that
the copy itself fits, not that the complete suite's peak fits.

An initial archive copy without `--no-preserve=ownership` failed because
capability dropping forbids restoring the image's file ownership. Its error
output also exceeded the child-process capture buffer. That container was
removed. The corrected diagnostic changed copy semantics, not capabilities
or memory protections; its container was also removed normally.

See the [saved assessment](../experiments/swe_bench_pro/v2_js_nodebb_upload_path/writable-dependencies-assessment-2026-10-14.json)
and reproducible helper `tools/assess_nodebb_writable_dependencies.cjs`.
No npm install, lifecycle scripts, repository code, public tests, image builds
or model calls were run by this assessment. No baseline setup was registered.

## Next boundary

The layout was introduced only in a separate connected lifecycle diagnostic,
described below. Keep the public tests and resource limits unchanged. npm may still
reconcile the whole NodeBB root, fetch additional packages or run dependency
lifecycle scripts; none of that is proven by a filesystem write check.
Do not disable scripts or omit tests to manufacture a successful baseline.

The copy assessment alone does not make NodeBB ready and does not enable
networking for agent-side candidate selection.

## Public lifecycle result

The requested install → upgrade → uninstall diagnostic passed on 14 October
2026. It ran the **five unchanged assertions** in NodeBB's public
`Plugins install/activate/uninstall` group: install, activation, invalid-ID
handling, upgrade and uninstall. The original test installs `1.0.16`, upgrades
to `latest` and checks removal from the root manifest. No npm lifecycle script
was disabled, and no public test source was edited.

`tools/run_nodebb_writable_lifecycle.py` replaces the shared dependency-linking
step with the assessed private copy in its own command wrapper, enables normal
networking and selects only that public group. Other repository helpers and
existing local edits were left untouched. The image stays read-only; the same
one CPU, 4 GiB memory, 4 GiB scratch, 2,048 PIDs and 30-minute cap apply.
There is no snapshot registry service or cache-supplement image.

All five cases passed, with no hook failures or aborted run. Total runner time
was 187.72 seconds; Mocha took 35.16 seconds. The reporter retains the full
file's inventory of 29 tests, so its full-file completion audit correctly stays
incomplete: the other 24 cases were deliberately not selected. A separate
exact-title check verifies all five requested cases rather than relabelling
that incomplete audit as full coverage. Fifteen focused wrapper/reporting
checks passed. See the [lifecycle evidence](../experiments/swe_bench_pro/v2_js_nodebb_upload_path/writable-lifecycle-2026-10-14.json)
for source hashes, all outcomes and report digests. Normal container/workspace
cleanup completed.

Next: run the unchanged complete public schedule with this private dependency
layout and normal networking, without the group filter. No full-suite retry
has started. NodeBB's full baseline remains unready until complete reporting is
verified; the previous full attempt remains 3,321 passes and one failure.
