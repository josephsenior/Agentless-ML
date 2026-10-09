# Adaptix: unchanged public baseline

This is the first, unchanged attempt. The subsequent
[candidate-helper fix and fresh baseline](deepswe-adaptix-helper-imports-2026-10-10.md)
resolved both collection errors, retaining all 2,824 passes and 28 skips.

Adaptix now supplies a passing regression inventory: **2,824 passed, 28 skipped
and two collection errors**, across 2,854 report IDs. The actual result is
**FAIL, exit 1**, not an all-green suite. The official survey marks it ready
under its existing completed-run/nonempty-passing-inventory rule. Overall
readiness is **104/113**: 101 published-image tasks and three registered modified
environments, with nine tasks remaining.

## What changed

Only the stale survey result was superseded. The old workspace provider refused
Git submodules before tests could start. The current provider accepts gitlinks
and clones with `--no-recurse-submodules`; regular candidate files remain
editable while submodule contents remain unavailable.

At base `a691069fcadf9131e5f7a5a130a022dc678f3e1d`, the only gitlink is
`benchmarks/release_data`, pinned to
`8e124e34a312ba44419dcfbf656f873b5281541b`. It holds performance-benchmark data.
The repository's default pytest configuration selects `tests` and `examples`;
tox has a separate benchmark schedule. No submodule was fetched or initialized.
The sealed source still reports the gitlink as uninitialized after this run.

## Exact attempt

- Task: `adaptix-name-mapping-aliases`.
- Original pinned image: `sha256:528654670f3c591e6491fc6fa01a0b8905bc8dee1b0557c5e76231bcc206f8fe`.
- No task override, environment registration, dependency installation or test edit.
- Existing command: `cd /tmp/work && PYTHONPATH=/tmp/work/src:/tmp/work python -m pytest -p no:cacheprovider --continue-on-collection-errors --junitxml=/tmp/report.xml "$@"`, with no selected targets.
- Execution: 27.419 seconds; complete survey attempt: 30.1 seconds.
- Unchanged cap: 1,800 seconds, 8,192 MiB memory with no extra swap, two CPUs,
  2,048 PIDs and 4,096 MiB temporary storage.

Live inspection of this attempt's container confirmed network `none`, read-only
root, all capabilities dropped, `no-new-privileges`, no privileged mode, no added
hosts or published ports, and `/tmp` mounted `rw,exec,nosuid,nodev`. The ordinary
survey record does not persist HostConfig for original-image tasks; its
`docker_protections` field is null. This confirmation came from live inspection,
not that field. The owned test container was removed after completion.

## Remaining caveat

Both collection errors are import-file mismatches for
`tests/tests_helpers/tests_helpers/misc.py` and `model_spec.py`. Python imported
`tests_helpers.misc` and `tests_helpers.model_spec` from `/app`, while pytest
tried to collect the candidate versions under `/tmp/work`.

This is not evidence that the benchmark-data submodule is needed. It is a
separate candidate-import problem: test helpers can come from the image checkout
rather than candidate source. The unchanged baseline establishes that the
submodule no longer blocks setup, but does not certify clean candidate-helper
provenance. A next, separately approved step is to assess putting the candidate
helper package first on the import path, then verify its origin before another
unchanged public schedule. No such change or second attempt was made here.

## Evidence

The append-only official survey is `../output/deepswe-survey/survey.jsonl`.
Raw artifacts are under
`../output/deepswe-survey/runs/adaptix-name-mapping-aliases/logs/agentless-ml-7a20dadc1df74871a22f10a72ea7e364/`.
The compact committed [record](../experiments/deepswe/adaptix_baseline_2026_10_10.json)
retains counts, error IDs, exact pins and artifact SHA-256 values.
