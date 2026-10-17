# Pebble: stable matching for randomized tests

> Development record. See [the documentation guide](../README.md) for current status.

The two saved public reports now replay to the same **13,640 matching units**:
13,612 passes, 10 failures and 18 skips, with zero cross-report regressions.
The raw reports still contain 14,279 and 14,273 results respectively. They
have not been rewritten; their hashes are recorded in the
[replay evidence](../../experiments/deepswe/pebble_parent_matching_2026_10_11.json).

## Why these six families

The pinned public source generates crash points, seeds, bitmap probabilities,
column schemas, integer configurations and a random endian-test input at runtime.
Those values appear in child names, so exact-ID comparison falsely treats
235 passing IDs in the earlier report as missing from the later report.
The six stable roots are:

- `pebble::TestDBCompactionCrash`
- `pebble/sstable::TestIterator_RandomErrors`
- `pebble/sstable/colblk::TestBitmapRandom`
- `pebble/sstable/colblk::TestBlockWriterRandomized`
- `pebble/sstable/colblk::TestUintsRandomized`
- `pebble/sstable/valblk::TestLittleEndianGetPut`

Each package above has the exact `github.com/cockroachdb/` prefix in the
allowlist. Matching requires that full root or its slash-delimited descendants.
Similarly named tests, other packages and every other task are unaffected.

## Matching contract

The Pebble-only `pebble-random-parent-v1` report policy aggregates each family
to its stable parent. This is not number masking or a claim that randomly
generated children represent identical inputs across runs.

A group passes only if an explicit parent and at least one descendant are
present and all their reported outcomes pass. Any child or parent failure/error
makes the group nonpassing, regardless of event order or later duplicate passes.
A skipped parent or descendant also prevents passing. Missing parent evidence,
or a parent without descendants, produces an error matching unit.
If the whole family is absent, existing baseline-ID matching counts that
missing parent as a regression. Partial or missing reports remain subject to
the normal Docker/report safeguards.

All public tests still run. Docker saves the original CTRF report, including
every child name and outcome. Only parsed matching units are grouped.
Raw test counts and matching-unit counts therefore intentionally differ.
Existing normalization collision rejection for Helm and Adaptix is unchanged;
the explicit Pebble family aggregation does not weaken it.

## Verification and limits

Host tests passed **206 checks**, with four existing opt-in checks skipped.
They exercise all six families, changed child names/counts, nested failures,
missing/skipped parents, skipped children, duplicate results, event order,
unrelated IDs and the CTRF-only policy. The existing failure counter is used
to verify that nonpassing or missing parents count as regressions.

`tools/replay_pebble_parent_reports.py REPORT_A REPORT_B` reproduces the saved
report comparison without Docker or source edits. Both reports have unchanged
SHA-256 hashes. No public suite, official survey or model call was run for this
change; readiness remains **109/113**.

Parent-level matching avoids identity noise, but does not remove stochastic
test behavior or prove equivalent coverage across random runs. A future real
candidate run must use the newly parsed baseline and the same registered
policy, not a previously serialized child-level regression inventory.

Next: inspect Wazero's remaining OOM blocker; the other three unready tasks
remain parked under the current limits.
