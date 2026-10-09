# Adaptix: stable regression IDs

Adaptix's 74 address-bearing test IDs now match across processes. A fresh official
baseline passed with **2,824 passed, 28 skipped, no errors and exit 0**. Every
normalized ID and outcome exactly matches the preceding successful run. Overall
readiness stays **104/113**.

## Decision

Some public parametrizations put Python reprs such as
`<function <lambda> at 0x7737e02dbba0>` or `<pkg.Provider object at 0x7737e0816d80>`
in test names. Their process addresses change even when the code and case are
unchanged. Exact report-ID matching would incorrectly count those baseline cases
as missing in a candidate run.

`TestReport.id_policy` now has an opt-in `python-repr-address-v1` policy, selected
only by `adaptix-pytest`. It replaces the address within those specific function
and object repr shapes with `{address}`. It retains the function/class name and
all other parameters, including ordinary hexadecimal values. Generic JUnit,
CTRF, Mocha and every other task retain their existing IDs.

This belongs in report interpretation, not in the repository's tests: changing
pytest parametrization would alter public test code, and rewriting the XML
would discard original evidence. The Docker runner parses the same raw XML with
the declared policy, so baseline and candidate results use the same keys before
regression inventory and failure counting. Execution metadata records the policy;
the raw `report.xml` remains byte-for-byte as pytest wrote it. Custom targets,
timeouts and command argument forwarding are unchanged.

## Collision handling

Removing an address alone is unsafe when two distinct raw IDs would map to the
same key. The parser detects this before accepting results and raises a report
error rather than merging them or assigning order-based suffixes. Order-based
IDs could attach results to different cases when a candidate changes discovery.
Exact repetitions of the same raw ID retain the existing worst-outcome rule.

A collision yields no partial per-test evidence. A nominally successful command
becomes a harness error; the existing rule for an already-proven regression
command that fails with an unusable report remains conservative (all counted
baseline cases fail). No colliding or missing case is promoted to passing.

This policy is not a general semantic identity system for arbitrary objects.
Future ambiguous parametrizations must be reviewed; they are not silently
accepted. Existing pre-policy inventories should be rebuilt with the policy,
not mixed with normalized candidate IDs. The recorded-workflow tool builds its
baseline using this same test plan.

## Verification

- The two earlier saved public reports yield identical mappings for all 2,824
  passes and 28 skips under the new policy. The first report's two collection
  errors remain errors; they were omitted only from this passing/skip comparison.
- The fresh unchanged public schedule again passed with 2,824 passes and 28
  skips. Its normalized IDs and statuses exactly equal the preceding successful
  report. Exactly 74 IDs change between raw and normalized parsing; all 2,852
  remain unique. No collisions occurred.
- Host checks cover changing addresses, lambda reprs, class/function distinction,
  unchanged literal hex, opt-in isolation, rejection of unknown policies and
  incompatible formats, collisions (including a literal marker), worst-outcome
  repeats, raw XML retention, Docker policy forwarding and real failure/missing
  case accounting. Final focused run: **173 passed, 12 opt-in checks skipped**.
  The broader earlier run including fixed-workflow tests also passed (201 passed,
  13 skipped) before the final collision-integration check was added.

The test script, assertions, default `tests`/`examples` schedule, candidate
import checks, original image and Docker limits did not change in this step.
The performance-data submodule remains uninitialized. The new attempt took
20.001 execution seconds and 22.4 survey seconds under the same 1,800-second cap,
8,192 MiB memory/no extra swap, two CPUs, 2,048 PIDs and 4,096 MiB temporary
storage, with the unchanged offline/read-only protections.

## Evidence

The append-only survey is `../output/deepswe-survey/survey.jsonl`.
Raw artifacts are under
`../output/deepswe-survey/runs/adaptix-name-mapping-aliases/logs/agentless-ml-39e5081ce9494cf09a41ddf7ba4bf714/`.
The [compact record](../experiments/deepswe/adaptix_stable_ids_2026_10_10.json)
retains pins, comparisons, counts, policy and artifact SHA-256 values. Previous
reports and execution records were not rewritten.
