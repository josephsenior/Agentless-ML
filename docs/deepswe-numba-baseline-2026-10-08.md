# Numba candidate build and public runner — 8 October 2026

The candidate build and imports are verified, but **Numba still has no usable
baseline**. Its full native serial schedule exceeded the existing 30-minute
timeout. The latest survey status is `timeout`, not `ready`; overall readiness
remains **100/113**, with 13 tasks needing attention.

## Why the old survey could not run tests

The old generic pytest result had 352 collection errors and no executed tests.
Numba's candidate source checkout lacked compiled native extensions, starting
with `numba.core.typeconv._typeconv`. The published image had built its own copy,
but those binaries would not reflect candidate changes.

The reviewed preparation runs the public development guide's
`python setup.py build_ext --inplace` inside the candidate checkout. A separate
check then verifies that Numba and six critical extension modules import from
`/tmp/work/numba`. The build and all seven import checks succeeded in the pinned
image, using its existing compiler and installed dependencies. No image binaries
or patched Python source were copied into the candidate. In particular, the
installed llvmlite is 0.47.0 and already satisfies the unmodified candidate's
minimum; the image's older version-check patch is unnecessary here.

## Why this also needs Numba's own test runner

The first rebuilt diagnostic retained generic pytest discovery. It collected
11,857 items and 15 collection errors, but also attempted CUDA-driver tests on
this container without a GPU. The public `numba/cuda/tests/__init__.py` has a
`load_tests` hook that includes those suites only when CUDA is available;
pytest does not respect that unittest hook. The owned diagnostic container was
stopped, and its incomplete result remains a `harness_error`, not a baseline.

The corrected `numba-runtests` override invokes the public root `runtests.py`
with no selectors or extra test flags. Numba retains its default full schedule,
custom loader, ordering and hardware-availability decisions. Its own output
confirms `skipped CUDA tests`. This is not a hand-picked CPU test list or a
new exclusion added by this project.

The image lacks optional `xmlrunner`. A small recorder therefore observes the
existing `BasicTestRunner`'s actual unittest results and emits JUnit after the
outer run finishes. It preserves normal result callbacks and exit behavior;
failures, errors, expected failures, unexpected successes, skips and failing
subtests remain visible. Nested runner probes inside Numba's own tests are not
mistaken for additional baseline tests. Duplicate IDs retain their worst
outcome, and incomplete, bootstrap-failed or empty runs produce no accepted
report. A timeout or native crash is never converted into a passing inventory.

## Reproduce and protections

The native run reached real test execution and reported passing, skipped and
expected-failure progress. Its public list mode enumerated 10,609 `numba.*`
test entries in this environment. The complete run did not finish before the
1,800-second command timeout, so no final JUnit report was produced or accepted.
The recorded `0/0` is therefore **zero accepted report cases**, not a claim that
Numba executed no tests or that every test failed.

Execution metadata reports 1,817.3 seconds including timeout handling; the
survey took 1,828.0 seconds including preparation and workspace cleanup. The
last output was still in CPU array-expression tests. Observed memory was about
5.6 GiB near the end, below the 8-GiB cap; the recorded outcome is a timeout,
not an OOM. No partial passes were promoted into the regression inventory.

Build output, seven candidate import confirmations, native runner output and
execution metadata are under
`../output/deepswe-survey/numba-stencil-boundary-modes/logs/agentless-ml-a7e2e3691822409bb6979a8a9255e382/`.
The earlier stopped pytest diagnostic is retained under
`../output/deepswe-survey/numba-stencil-boundary-modes/logs/agentless-ml-c745e9c954b44cb6926010d127751322/`.
Both owned containers and temporary candidate workspaces were cleaned up.

The next step is to assess Numba's supported two-process runner against the
same CPU, memory and time limits before approving another long retry. Two
processes must not be assumed to fit: the serial run already used substantial
memory. This milestone did not enable parallel test execution, extend the
timeout, increase memory or narrow the schedule.

The sealed base is `5781334aa654972fdc749003e7c1e93e6d277110`. The verified
published image remains
`sha256:d30747d56f59cb61bb9a4e87ba8dc4df29ccbb471a1a1146f20d5d9d58fa90ac`.
No dependency or test was changed. The runner retains offline networking,
read-only root filesystem, normal capability restrictions, 8-GiB memory, two
CPUs, 4-GiB temporary storage, 2,048 PIDs and a 1,800-second timeout.

```powershell
.\.venv\Scripts\python.exe tools/survey_deepswe.py `
  --tasks-root ../benchmarks/deepswe/corpus/tasks `
  --repositories ../benchmarks/deepswe/repos `
  --task-id numba-stencil-boundary-modes --rerun `
  --results ../output/deepswe-survey/survey.jsonl `
  --artifacts ../output/deepswe-survey --timeout-seconds 1800
```

The focused execution, reporter, adapter and report suites passed: 145 passed,
five skipped. The full project suite passed: 677 passed, 31 skipped.
Held-out tests and solutions were not inspected, and no model was called.
