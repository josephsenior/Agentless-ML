# Wazero: short-mode diagnostic under the published limits

One separately labelled **short-mode diagnostic** passed with **155,923 passes,
44 skips and no failures**. Peak cgroup memory was **1,431,605,248 bytes (1.33 GiB)**,
with all final memory-event counters zero and Docker `OOMKilled=false`.

This is **not a full baseline**. Wazero remains officially out-of-memory for
the full public schedule, and overall readiness remains **109/113**.

## What ran

`tools/run_wazero_short_diagnostic.py` ran:

```text
go test -json -count=1 -short -p 1 -parallel 1 ./...
```

It reused the ordinary Go command, candidate-source compilation and streaming
CTRF converter, adding only the three approved flags. It used the original
image and sealed base revision, recorded in the
[evidence summary](../experiments/deepswe/wazero_short_diagnostic_2026_10_11.json).

Live/final inspection confirmed 8 GiB RAM without extra swap, two CPUs, 2,048
PIDs, 4 GiB tmpfs, no network, read-only root, dropped capabilities and
no-new-privileges, without privileged mode, host binds, added hosts or ports.
No build cache was seeded, earlier-GC environment added, source/assertion
patched, or permanent override registered. The 1,800-second command cap stayed
unchanged. All existing root-module `./...` targets were retained; this is not
a claim to execute the extra nested-module commands in upstream `make test`.

Docker was initially stopped. The first launch failed during image inspection,
before any container or tests started. Docker Desktop was then started using
its existing settings, and exactly one diagnostic test attempt ran. No host
power settings were changed.

## Coverage is deliberately reduced

The pinned source has ten short-mode branches: three skip workloads and seven
reduce internal stress/concurrency. The earlier successful 16 GiB full-schedule
report had 155,928 passes and 39 skips. Comparing saved reports identifies these
five previously passing outcomes that short mode now skips:

- `TestEngineCompiler/huge_binary`
- `TestEngineInterpreter/huge_binary`
- `TestMemoryLeak`
- `Test733/interpreter/store_higher_offset`
- `Test733/compiler/store_higher_offset`

Both huge-binary variants use the same public guard, and both store-offset
variants use another, so three source skip branches yield five additional
skipped results. The seven other branches reduce mutex/atomic, engine hammer
and store hammer workloads. Their IDs may remain unchanged while their stress
coverage differs. Equal total result counts do not imply equal coverage.

Upstream CI uses short mode in some jobs but also runs non-short jobs.
This diagnostic is supported by upstream test code, not equivalent to the
full upstream CI matrix or our full public baseline.

## Evidence and limits

The run took **415.68 seconds including snapshot preparation and setup**.
Twenty incremental resource samples were saved. The largest UTC sample gap
was 54.14 seconds; the journal is not continuous process tracing. Final cgroup
peak and counters provide stronger memory evidence than the sampling interval.
The owned container and temporary checkout were cleaned up.

The compact summary hashes the raw CTRF, execution record, resource journal,
bounded last 1 MiB Go event tail and diagnostic record. Host checks passed
12 tests. Raw artifacts live separately under
`../output/deepswe-diagnostics/wazero-short-8g/`; the official survey and
task configuration were not changed, and no retry was started.

One unrelated ID also changes between reports:
`api::TestEncodeDecodeExternRef/<pointer-like value>`.
This has not been normalized. The diagnostic does not establish reliable
per-ID candidate regression matching.

Next: decide whether this explicitly reduced schedule is useful as a separate
experimental condition, or keep Wazero parked for full-schedule validation at
8 GiB. Do not register it as a recovered full baseline.
