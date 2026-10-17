# Numba: registered public validation and 113/113 readiness

Numba's verified public-validation setup is now shared by the survey,
standalone public-test command and recorded candidate workflow. The registered
override specifies **10,800 seconds per public command**, replacing the former
1,800-second default for this task. An explicit CLI or experiment timeout still
takes precedence. Other tasks retain their existing defaults.

The command builds native extensions from the candidate, checks candidate
imports, and executes the full native schedule with `-m 2`. It keeps the
writable `XDG_CACHE_HOME=/tmp/numba-user-cache`, `OPENBLAS_NUM_THREADS=1`,
original pinned image, two CPUs, 8 GiB RAM, disposable disk scratch,
Docker-default swap and offline network. Numba's own thread maximum stays
unchanged. Both the host and container enforce the chosen command cap.

## Evidence reused, with no new full run

The registered command was compared directly with `execution.json` from the
[completed cache-corrected baseline](deepswe-numba-writable-cache-2026-10-17.md).
Its complete argument vector, report contract and timeout match. Artifact
SHA-256 values were verified before registration. That run retained all
10,609 unique IDs: **9,991 passed, zero failures/errors, 595 skips and 23
expected failures**. No new tests or model calls ran for this refresh.

One readiness record was appended to the local survey, explicitly labelled
`evidence_reused`, with the original artifact paths, hashes and execution
duration. Every byte of the earlier survey records was preserved, including
Numba's old timeout. The latest record now marks Numba ready, yielding
**113 ready / 113 tasks**. The
[compact registration evidence](../../experiments/deepswe/numba_registered_readiness_2026_10_17.json)
retains the previous and new records and the survey hashes before and after.

Fourteen focused registration checks passed, covering the shared command,
worker count, timeout defaults, explicit shorter allowances and invalid
override values. The other execution checks passed apart from the two stale
expectations corrected and rechecked here; four opt-in Docker checks were
skipped. No benchmark rerun was launched.

## What the count means

All 113 tasks now have usable public baselines under their declared profiles.
Numba uses an extended public-command allowance, and Testem, Cliffy, GoReleaser
and Pwntools use registered supplemented images. This is not a claim that
Numba finishes under the former 30-minute cap or that all tasks have been
solved. The corpus agent budget and held-out verifier settings were not changed.
The research protocol remains a draft; it must account for the cost of running
this schedule for multiple candidates.
