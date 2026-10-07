# Pwntools public doctests — 7 October 2026

Pwntools now uses its public Sphinx doctest runner instead of pytest. The
published image still cannot run it: Sphinx is absent. A separate image with
the documentation dependencies gets into the real suite, but the full
baseline remains unfinished. DeepSWE readiness stays **92/113**.

## What changed

The repository's `TESTING.md` says to run `PWNLIB_NOTERM=1 make -C docs
doctest`. Examples come from both RST files and Python docstrings through
Sphinx's autodoc extension. A plain pytest or stdlib doctest invocation would
miss the public setup, shared namespaces and custom platform flags.

The reviewed task override now invokes Sphinx with the Makefile's doctest
arguments, using the candidate's public configuration and source. A small
observer records document/group outcomes as CTRF. It delegates execution to
the public platform-aware builder rather than replacing that builder.

Passing setup is not a passing test. Groups with setup or cleanup failures
are errors; groups with any failed example fail. Only a group with executed
examples and no failures passes. This is deliberately coarser than per-example
reporting: one broken example excludes its whole group from regression
selection. It does not suppress failures to recover more passing tests.

## Separate dependency environment

The [build recipe](../experiments/deepswe/pwntools/README.md) adds sixteen pinned
documentation packages in a virtual environment over the published image.
Sphinx 8.1.3 and autoprogram 0.1.5 satisfy the public requirements. Existing
runtime package versions are unchanged; the virtual environment shadows pip
25.3 with its bootstrap pip 25.0.1. The version delta, download URLs and wheel
hashes are in [dependencies.json](../experiments/deepswe/pwntools/dependencies.json).
`pip check` passed.

Only the build downloads dependencies. Test execution remains offline, with
the usual read-only root, 8-GiB memory limit and two CPUs. The original image
and canonical pin were not changed. No model or held-out task tests were used.

## What the live checks showed

The published-image rerun stops with `ModuleNotFoundError: No module named
'sphinx'`. It produces no accepted test report and remains a harness error.

The augmented-image diagnostic starts the actual public examples. Its logs
show missing GDB and a missing MIPS assembler, plus cascading failures in
debugger examples. Pwntools' own ten-minute alarm was preserved, but the run
continued to stall. We stopped the verified doctest process with SIGTERM
after **825 seconds**, retaining the logs before the runner cleaned up its
temporary container.

That exit 143 is an **interrupted diagnostic**, not a completed baseline,
not a timeout at the declared 1,800-second limit, and not a failed repair.
No structured inventory was accepted. Zero reported cases does not mean
zero examples ran. We have not established whether an uninterrupted run would
finish within the cap or how many groups would pass.

The full diagnostic used the first derived image. A later version-locked
rebuild added the installation manifest; dependency versions read from the
first running container match the final image. The final image was checked
with a focused candidate/config probe, not another full baseline.

That probe changes a module only in a temporary candidate checkout and limits
Sphinx discovery to a synthetic document while retaining the public config.
It confirms that the candidate marker is visible, SKIP and platform filtering
work, a deliberate test failure is reported, and setup/cleanup failures cannot
become passes. The resulting four groups are one pass, one failure and two
errors, exactly as intended. These are authored checks, not benchmark tests
or evidence of task resolution.

## Remaining boundary

Verification: **611 framework tests passed, 24 skipped**. The separately
enabled Pwntools tests, including the live Docker probe, passed **8/8**.
`git diff --check` was clean.

The public setup also installs native tools and prepares SSH users, keys and
a local service. We did not run those system-changing scripts, add test
exclusions, spoof their expected user, enable network access or borrow the
image's unpatched source.

The runner plumbing is now checked. Recovering a full Pwntools baseline needs
a separately reviewed machine environment, not another change to localization
or repair. Until that is agreed and tested, this task remains blocked and
outside canonical readiness.

[Machine-readable evidence](../experiments/deepswe/pwntools_doctest_2026_10_07.json)
records image identities, resources, execution-file hashes, the interruption
and the final candidate probe. Raw logs remain outside Git under
`../output/deepswe-survey/`.
