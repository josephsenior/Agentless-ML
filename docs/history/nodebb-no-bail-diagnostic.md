# Explicit no-bail NodeBB diagnostic

> Development record. See [the documentation guide](../README.md) for current status.

This mode collects the complete public inventory while retaining baseline
failures. It is not the repository-default schedule or an official result.

Run `tools/run_nodebb_writable_lifecycle.py` with `--full-suite`,
`--no-bail-diagnostic` and a new `--output` directory. The new mode adds only
`--no-bail` to the verified writable-copy full command, leaving the public
configuration and all test sources unchanged. It is rejected without
`--full-suite`. The same original image, fresh sealed base, live networking,
private dependencies and CPU/memory/scratch/PID/30-minute limits apply.

There is no exclusion list, forced-success wrapper or disabled npm lifecycle
script. Raw and individual reports retain failures and the command's nonzero
exit is preserved. `diagnostic_inventory_complete` requires a complete audited
inventory, with no missing cases, conflicting counts, hook failure or abort.
This mode never promotes itself to `full_suite_ready`, an official score or an
offline candidate-selection condition.

## Result on 14 October 2026

One attempt completed with **8,089 passes, three failures and no skips**.
All 8,092 registered tests ended: 2,011 were present initially and 6,081 were
added during execution. There were no missing or unexpected cases, hook
failures or aborts. Raw and individual reports agree. The command exited 3,
retaining all failures. Runner time was 462.03 seconds including preparation;
Mocha took 262.68 seconds.

The failures are:

- The actor-URL assertion at `test/activitypub/actors.js:59`: the
  [previously diagnosed field mismatch](nodebb-activitypub-assertion.md).
- The category-actor assertion at `test/activitypub/actors.js:169`: its summary
  includes appended explanatory HTML while the test expects only the category
  description.
- The Azerbaijani translation inventory at `test/i18n.js:118`:
  `_DO_NOT_EDIT_FILES_HERE.md` is present in the source-language directory but
  absent in `az`.

The [subsequent source investigation](nodebb-additional-baseline-failures.md)
explains both as existing pinned-base mismatches, also present in the original
image. As in the earlier dynamic
test report, all three entries report `test/utils.js`; their assertion-stack
locations are saved separately, not silently substituted. No failure was
excluded, changed into a pass or hidden by the inventory-complete flag.

See the [diagnostic evidence](../../experiments/swe_bench_pro/v2_js_nodebb_upload_path/no-bail-diagnostic-2026-10-14.json)
for outcomes, limits and report hashes. Raw reports remain in the parent
workspace's `output/swe-bench-pro-v2-readiness/2026-10-14-nodebb-no-bail`.
Container/workspace cleanup completed. Eighteen focused checks passed. No
official verifier, model call or further retry ran.

The two newly exposed failures were investigated without modifying the tests.
A complete diagnostic inventory is now available, but using it for regression
validation needs explicit review of existing failures, the non-default bail
policy and matching network/setup conditions. Do not keep retrying merely to
seek a green result.
