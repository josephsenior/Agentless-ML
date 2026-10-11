# Multiple reproduction samples on the real fd task

The existing controller selected the expected reproduction from five recorded
inputs on `fd-deterministic-multi-key-sorting`. Selection is verified; the later
public regression and repair/export stages of this run did not finish.

These are deliberately constructed controls, not independent model samples.
They test the selection mechanism, not model quality. No model was called.

| Sample index | Recorded input | Observed base result | Eligible? |
| --- | --- | --- | --- |
| 0 | Text without fenced Rust source | Parse error; not executed | No |
| 1 | Public `fd --version` check | Pass | No |
| 2 | Smaller issue-derived `--sort path` check | Fail | Yes |
| 3 | Existing global path-sorting reproduction | Fail | Yes |
| 4 | Intentional exact-source duplicate of sample 3 | Fail | Yes |

Each of the four parseable samples ran in its own pinned workspace and Docker
execution. The three failures were ordinary assertion failures: the base CLI
rejects the requested `--sort` option. The raw nextest JUnit embedded in each
report agrees with its recorded outcome; none is a build error or skipped test.

The eligible indices were **2, 3 and 4**. With `exact-source-v1`, samples 3 and 4
form a two-vote group, beating the earlier, distinct sample 2. The controller
selected **sample 3**, the earlier member of the winning group, and froze its
source with SHA256
`ad9d28ff518a2260f87e9891e2f25bfdb146e954b67abe684af155d4fb5a0d30`.
The duplicate was executed separately; it was not given a borrowed result.

## What stopped, and what this does not prove

Selection artifacts were saved, but no candidate validation or final prediction
was saved. When inspected afterward, the original Python process was gone and
Docker's Linux engine pipe was unavailable. We have not established why the
process stopped. No retry was started, and the interrupted workspace was kept.

This run therefore does **not** establish a complete pooled controller replay,
public-regression preservation after repair, or selection-before-validation
timing against an observed candidate. The earlier
[single-reproduction combined run](fd-issue-derived-reproduction.md) remains
separate evidence; its results are not substituted here.

The image, base revision and limits were unchanged: 4096 MiB memory, 4096 MiB
tmpfs, one CPU, 2048 PIDs and a 600-second cap per check. Docker retained its
offline network, read-only root, dropped capabilities and no-new-privileges
protections. No held-out verifier ran. DeepSWE readiness remains **109/113**.

## Evidence and replay

The [recorded inputs](../experiments/deepswe/fd_reproduction_samples/experiment.json)
describe the controls. The
[checkpoint evidence](../experiments/reproduction/fd_sample_selection_2026-10-11.json)
records the task pins, observed selection, report hashes and incomplete stages.
Local artifacts are under `artifacts/fd-reproduction-samples-20261011`.

The saved checkpoint can be audited without Docker:

```powershell
$env:PYTHONPATH='src'
.venv/Scripts/python.exe tools/run_fd_path_sort_reproduction.py --audit-selection-only --output artifacts/fd-reproduction-samples-20261011 --tasks-root ../benchmarks/deepswe/corpus/tasks --repositories ../benchmarks/deepswe/repos
```

A fresh complete replay, if requested, needs Docker running and a new output
directory. This command has not been retried:

```powershell
$env:PYTHONPATH='src'
.venv/Scripts/python.exe tools/run_fd_path_sort_reproduction.py --multiple-reproduction-samples --with-public-regressions --output artifacts/fd-samples-new --tasks-root ../benchmarks/deepswe/corpus/tasks --repositories ../benchmarks/deepswe/repos
```

The related fixture, Rust/controller, selection and report checks passed
**190 tests**, with 12 opt-in tests skipped. Those tests are separate from the
four completed real sample executions. Saved-record tests reject wrong winners,
vote counts, eligibility, frozen sources, outcomes and candidate ordering; they
also distinguish an incomplete selection checkpoint from a completed replay.
