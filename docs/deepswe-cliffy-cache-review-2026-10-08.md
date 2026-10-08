# Cliffy: an incomplete published Deno cache

Cliffy's pinned image contains Deno 2.0.0 and a 21-MB dependency cache at
`/deno-cache`. Unlike GoReleaser, this directory is not hidden by our `/tmp`
mount: the existing Deno runner copies it into writable `/tmp/deno-cache`
before running the unchanged public schedule with `--cached-only`.

The latest saved baseline fails before producing a report because
`https://jsr.io/@std/io/meta.json` is absent. Removing `--cached-only` would not
fix an offline run, and enabling test-time networking is not the proposed fix.

## What the image actually contains

Task: `cliffy-config-file-parsing`.
Public base: `132a437c40cffbdfbe474ca808c8debde59e2633`.
Pinned image:

```
sha256:0a8dd8f1270ec4bb88efadad3021762e1d07274f686276c8a484d26a00bd91b5
```

The public environment Dockerfile primarily caches command/flags entry points,
selected standard modules and a subset of test paths. Its test-file cache
loop suppresses errors with `|| true`, so successful image construction is not
proof that the full repository's test imports are available offline.

The read-only cache inventory found no files or package metadata for these
eight packages declared in the root import map:

- `@c4spar/mock-command` (`^1.0.1`).
- `@c4spar/mock-fetch` (`^1.0.0`).
- `@std/async` (`^1.1.1`).
- `@std/cli` (`^1.0.27`).
- `@std/datetime` (`~0.225.7`).
- `@std/http` (`^1.0.24`).
- `@std/io` (`~0.225.3`).
- `@std/semver` (`^1.0.8`).

These are missing declared packages, not eight independently observed test
failures. Public source confirms that `@std/io` is used by ANSI and prompt
code, `@std/datetime` by prompt integration tests, the mock libraries by
command upgrade-provider tests, and `@std/semver` by upgrade-provider code.
Some other aliases appear only in examples or comments; do not claim that
every import-map entry must be fetched to execute this schedule.

The cache does contain package metadata for assert, encoding, fmt, fs, path,
testing and text, plus transitive internal. Cached version metadata includes
assert 1.0.19, encoding 1.0.10, fmt 1.0.10, fs 1.0.24, path 1.1.5, testing
1.0.0 and 1.0.19, text 1.0.19 and internal 1.0.14. This does not prove every
required source file, subpath or transitive dependency of those packages is
cached. Installed npm cache directories were observed, but complete npm
coverage was not audited here.

## Reproducible inspection

`tools/inspect_cliffy_deno_cache.py` reads only the image's public
`/app/deno.json` and the JSR cache directory. It observes Deno 2.0's trailing
URL metadata in cached files; all inspected files had a recognized URL. It
does not execute test code, resolve version ranges online or read held-out
task data. The inventory distinguishes metadata presence from complete graph
coverage. Two focused tests passed, including cached-source-without-metadata
and trailing-URL handling.

```powershell
Get-Content tools/inspect_cliffy_deno_cache.py -Raw | docker run --rm -i --pull=never --network=none --read-only --cap-drop=ALL --security-opt=no-new-privileges --memory=8192m --memory-swap=8192m --cpus=2 --pids-limit=2048 --entrypoint=python sha256:0a8dd8f1270ec4bb88efadad3021762e1d07274f686276c8a484d26a00bd91b5 -
```

All inspection containers were disposable, offline and read-only, without
host mounts, under the existing CPU/memory/PID protections. No dependencies
were downloaded, image built, tests rerun or runtime limits changed.

## Next step

Assess a separately labelled dependency-cache supplement. Preserve the cached
versions already available; resolve only required missing public dependency
graphs, record exact versions and checksums, and verify compatibility with the
unchanged Deno 2.0.0 binary. The root config disables locking and uses version
ranges, so blindly caching today's latest matching versions would introduce
unrecorded dependency drift.

Fetching missing dependencies and building a supplemented image are not part
of this inspection. If approved, perform dependency acquisition separately
from candidate execution, then test the unchanged full public schedule offline
under the same limits. Any substituted-image outcome must stay distinct from
canonical readiness. Do not remove packages from the schedule, disable type
checking, alter tests or allow test-time internet access to obtain a pass.

Original failure evidence:
`../output/deepswe-survey/cliffy-config-file-parsing/logs/agentless-ml-a55f4d94eea3446183c6697dd957f9a1/`.
The official survey remains **100/113 ready**; Cliffy remains unready and
Numba remains parked.
