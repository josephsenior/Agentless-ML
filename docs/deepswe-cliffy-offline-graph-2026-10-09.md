# Cliffy: supplemented cache and offline import check

The separate cache-supplemented image now passes Cliffy's native full test
discovery and type checking offline with the original **Deno 2.0.0** binary.
The successful check took **21.3 seconds**, returned **0**, and logged checks
for **119 candidate test modules**. No tests executed and no regression
inventory was accepted. Canonical readiness remains **100/113**.

## The separate image

The parent is the unchanged published image:

```
sha256:0a8dd8f1270ec4bb88efadad3021762e1d07274f686276c8a484d26a00bd91b5
```

The successful derivative, tagged `agentless-ml/cliffy-cache:2026-10-09`, is:

```
sha256:9e49eb0e15b12e2fbded70acbcb9a4f0948bbdbc731539299e0e99bd68ff27c9
```

`tools/build_cliffy_cache_image.py` rechecks every saved artifact's SHA256 and
size before staging it. It adds verified source and version metadata in the
cache encoding observed in the exact Deno 2.0 image. This is environment data,
not candidate code. The Docker recipe copies absent cache entries only; existing
cache entries, the repository and Deno binary are not overwritten. Build-time
networking is disabled, and the parent is pinned by digest with pulling disabled.

For missing package-wide indexes, the builder exposes only versions represented
by verified artifacts. Those index bodies are deliberately curated availability
snapshots, not byte-identical registry responses or publisher-signed indexes.
Both the source snapshot hash and generated body hash are recorded. Existing
image indexes are retained unchanged, including their original range-resolution
choices. Merely staging a curated replacement does not mean it overwrote an
existing index: the copy is no-clobber.

The audit's declared minimum pins are not a forced resolution lock. For example,
the new async index contains both verified 1.1.1 and 1.4.0, so a compatible range
may select 1.4.0. This remains an explicitly substituted dependency condition,
not evidence of the benchmark's historical dependency resolution.

## What the first check revealed

The first derivative was
`sha256:121c16e42178adbeb18f865dccdf24f7d7531635846d612be5547afd7eab7689`.
Its offline no-run check stopped in **18.0 seconds** on missing
`@std/assert/0.225.3_meta.json`, imported through mock-fetch 1.0.0. We had verified
the declared minimum 0.225.2, but the retained image index resolved the range
to 0.225.3. The error was retained; no test was run and no range was changed.

Inspection confirmed that the parent index lists assert 0.225.0 through 0.225.3;
its legacy internal index lists 0.225.0 and 0.225.1. Assert **0.225.3** was then
verified against the public registry, including all **55** source files. Its
version metadata SHA256 is
`b3c2847aecf6955b50644cdb9cf072004ea3d1998dd7579fc0acb99dbb23bd4f`.
The committed artifact manifest now covers **29 package/version pairs and
1,011 files**, up from the preceding audit's 28/956. The additional version did
not replace either older verified assert version or the cached newer assert.

The supplemented image was rebuilt offline and checked again. This was a
cache-preparation correction, not an automatic benchmark-test retry. Each
build's evidence is retained under its image ID rather than discarding the
first outcome.

## What passed, and what remains to run

`tools/check_cliffy_offline_graph.py` uses the existing Deno command, with only
`--no-run` added. It retains default whole-repository test discovery, candidate
source, the original public permissions and parallel flag, and `--cached-only`.
It declares no test report: a successful compile-only command is not a passing
test suite or regression inventory. The command ran inside a fresh candidate
checkout at `132a437c40cffbdfbe474ca808c8debde59e2633`, not the image's `/app`.

The Docker runtime kept networking disabled, a read-only root, dropped
capabilities, no-new-privileges, 8-GiB memory, two CPUs, 4-GiB temporary storage
and the 2,048 PID limit. Native test imports and type checking passed with these
protections. No checking was disabled, no tests filtered and no source patched.
The owned containers and candidate clones were cleaned up normally.

This establishes that the native compile-time test import graph can resolve
offline in this labelled environment. It does not establish that runtime-only
imports or subprocess fixtures are all covered, or that tests will pass. Those
questions require the unchanged public test run; none has been started yet.
The broader unused npm package graph is not independently certified by this
result. The earlier artifact manifest's compatibility flags describe the audit
stage, not this later successful compile-only observation.

Sixteen focused tests passed, covering artifact tampering, checksum audits,
cache-key/footer encoding and preservation of native discovery with no-run.

```powershell
.\.venv\Scripts\python.exe tools/build_cliffy_cache_image.py
.\.venv\Scripts\python.exe tools/check_cliffy_offline_graph.py --image-id sha256:9e49eb0e15b12e2fbded70acbcb9a4f0948bbdbc731539299e0e99bd68ff27c9
```

Build evidence is in `../output/deepswe-survey/cliffy-cache/build.json` and the
image-ID-specific `build-*.json` records. The successful manifest's byte SHA256
at build time is `2ca1b8999c367e7fd581e189fb7f2713b85404c866c120ae971a735c58d72be6`;
it identifies the actual staged working-copy bytes, including line endings.
Git may normalize that JSON's line endings without changing its parsed pins.

Graph evidence under `../output/deepswe-survey/cliffy-cache/logs/`:

- `agentless-ml-9f111b00e45a41d59f7d082804e72c3d/`: first missing-version result.
- `agentless-ml-44b3b51825f64c18b2fbcec5b9252cd8/`: successful no-run check,
  including `graph-check.json`, `execution.json` and command logs.

Next: one unchanged full public test attempt against this exact derivative,
offline and under the same limits, recorded separately from canonical readiness.
Numba remains parked.

The subsequent approved [full public run](deepswe-cliffy-public-baseline-2026-10-09.md)
passed in 58.8 seconds of host execution: 822 native tests and 76 steps,
898 raw passing JUnit entries and 878 distinct normalized regression IDs.
No failures or skips were reported. The duplicate-label count is documented,
and canonical readiness remains unchanged because this is a substituted image.
