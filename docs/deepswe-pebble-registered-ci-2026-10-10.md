# Pebble: registered public CI setup

Pebble's official survey refresh is **ready**, bringing the total to **109/113**.
The full public schedule returned **14,245 passes, 10 failures and 18 skips**
in 387.3 seconds including setup. All three upstream huge-memory row-block tests
remained skipped. The ten failed IDs are the same nine lint children and their
parent seen in the [CI diagnostic](deepswe-pebble-ci-mode-2026-10-10.md).
Exit 1 is preserved; ready means a usable passing baseline, not an all-green suite.

## Registration review

The task now selects `pebble-go-ci` in `test_overrides.json`. This reuses
the ordinary Go command and reporter, adding only `export CI=1` and `-p 1`.
It retains the complete `./...` target, candidate compilation, cold writable
cache, failure exits and 1,800-second cap. Other tasks' Go commands are unchanged.

The survey, standalone public-test tool and workflow all load this same override.
Consequently baseline and candidate public validation receive the same setup.
There is no environment-image substitution, new schema or held-out scorer change.
The original image digest and repository commit are preserved.

Live inspection confirmed the original 8 GiB RAM/no extra swap, two CPUs,
2,048 PIDs, 4 GiB tmpfs, offline network, read-only root, dropped capabilities
and no-new-privileges, without host binds, added hosts or published ports.
The last observed memory peak was 2,322,468,864 bytes and all memory-event
counters were zero. This is a live observation, not a saved final peak.
The completed runner result was an ordinary test failure, not OOM or timeout.

## Evidence and remaining caveat

The official append-only survey received one new Pebble record; no other task
was rerun. [Compact evidence](../experiments/deepswe/pebble_registered_ci_2026_10_10.json)
preserves that record and hashes its raw report and execution logs.
The owned container and temporary workspace were cleaned up.
Host checks passed 166 tests; five opt-in checks were skipped.

The diagnostic and official reports differ in randomized subtest IDs, including
crash `k=` values and random seeds; their total counts differ by six. Do not
interpret the smaller count as a filtered schedule, or assume exact per-ID
regression matching is already reliable. No normalization or randomness change
was introduced here. Before using Pebble for candidate ranking, inspect these
dynamic IDs and choose a conservative, collision-safe matching approach.

Current readiness is 106 tasks with original images plus three explicitly
registered modified images. The remaining four tasks are Numba, KGateway,
Pwntools and Wazero; the first three remain parked under current limits.
