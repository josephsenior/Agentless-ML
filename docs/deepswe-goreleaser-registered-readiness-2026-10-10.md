# GoReleaser: registered cache relocation and official survey

GoReleaser is now **ready** in the official survey, with **2,907 passed,
46 failed and 47 skipped** across 3,000 report IDs. The test command's actual
result remains **FAIL, exit 1**. Ready means it supplies a usable passing
regression inventory; it does not mean the full suite passed.

The fresh attempt took **404.953 seconds** for execution and 411.9 seconds
including survey preparation and cleanup. Overall readiness is **103/113**,
with ten tasks remaining: 100 ready in published pinned images and three in
explicitly registered modified environments (Testem, Cliffy and GoReleaser).

## Exact registered setup

The [environment registry](../experiments/deepswe/environments.json) binds
GoReleaser's base `399ef141161f212f4e81b5d7497b84633fc712d9` and original image
`sha256:778c43a00bb317e8e0b266b212b187be7765a12dbdadde3ba2f4bceba9c40080`
to the reviewed derivative
`sha256:a02ee6ffddb93fa736a2d8d345669d966a3c15db99d4333f151eeb1c08fed085`.
The published corpus pin is unchanged. Registration stays explicitly labelled
as a modified environment and is shared by the survey, standalone public-test
tool and recorded workflow. The held-out scorer is not changed.

The image moves its existing module/toolchain cache and build-cache seed out
of `/tmp`, where the runner's fresh temporary mount would otherwise hide them.
It selects the existing Go 1.26.1 binary, whose SHA-256 was checked in both
parent and derivative during review:
`548e61b2d08ae52043be2f1924ed3c1d2b2c41967e360f3e317667f6fa912fc2`.
No new toolchain, dependency download, source patch or rebuild was needed to
register this already verified image.

Registration also includes the tested setup command: copy the content-addressed
build-cache seed into writable `/tmp/go-build` before the existing Go command.
An image swap alone would omit this step. The shared setup helper produces
exactly the earlier diagnostic command at the standard 1,800-second cap; it
also preserves a caller's shorter cap and selected targets when explicitly
requested. No service or hostname mapping is added.

## What is unchanged, and what is not

The full survey plan remains `go test -json -count=1 ./...` against the fresh
candidate checkout, with the existing CTRF converter. `-count=1` disables test
result caching; Go's build cache is not a substitute for candidate source and
its content keys determine recompilation. The wrapper retains the original
test exit code, report and failure-code contract. Its container-side deadline
covers seeding, tests and conversion, alongside the unchanged host timeout.
This is the existing full-package plan, not a claim of parity with every
race/coverage flag in the repository's separate Taskfile recipe.

The image explicitly changes `PATH`, `GOMODCACHE`, `GOTOOLCHAIN=local` and
`GOPROXY=off`. Subprocess-based tests can inherit those settings. The previous
completed diagnostic had 2,907 passed, 46 failed and 47 skipped report IDs;
the exact causes of those failures remain undiagnosed. Do not attribute them
all to networking or treat them as harmless.

The registration guard accepts a completed report-bearing PASS or FAIL with
a nonempty passing inventory and the successful module check, matching the
existing survey eligibility rule. It does not accept a timeout, harness failure
or empty inventory. Failed and skipped baseline cases remain visible in the
report; they are not promoted into the passing regression inventory. Testem's
and Cliffy's existing verification guards are unchanged.

Fifty focused host checks passed before the official attempt, including exact
command equality, custom-timeout preservation, rejection of unusable or
mismatched evidence, and the existing Testem/Cliffy behavior. These checks are
not benchmark outcomes. The registration itself does not change readiness;
only a fresh appended survey result does.

## Fresh official result and evidence

Only GoReleaser was rerun. Its new record was appended to
`../output/deepswe-survey/survey.jsonl`; the earlier original-image harness
failure remains in that file. The fresh passing, failed and skipped ID sets
each match the completed cache diagnostic exactly, using case-sensitive
normalized IDs. Go reports parent tests and subtests separately, so the 3,000
IDs are not 3,000 independent assertions. No report parsing rule changed.

Observed Docker configuration retained network=none, read-only root,
cap-drop=ALL, no-new-privileges, 8 GiB memory with no extra swap, two CPUs,
2,048 PIDs, the same 4 GiB executable/nosuid/nodev /tmp, no privileged mode,
no extra hostname mapping and no published ports. The owned container was
removed and scoped Windows keep-awake request released. No persistent power
setting was changed. No further retry started.

The latest survey contains 103 ready, five unsupported repositories, two
harness errors, two out-of-memory outcomes and one timeout. The
[committed refresh record](../experiments/deepswe/goreleaser_registered_readiness_2026_10_10.json)
keeps the prior/fresh survey records, actual FAIL result and exit code,
46 failed IDs, protections, comparison with the earlier diagnostic, remaining
tasks and report digest. Raw `execution.json`, `report.json` and command logs:
`../output/deepswe-survey/runs/goreleaser-retry-publish-auditing/logs/agentless-ml-5aeb357246214211b1b1600383db90f1/`.
The converter retains terminal outcomes rather than full assertion messages;
the 46 failures have not been diagnosed or dismissed.

With the project virtual environment and `PYTHONPATH=src`:

```text
python tools/survey_deepswe.py --tasks-root ../benchmarks/deepswe/corpus/tasks --repositories ../benchmarks/deepswe/repos --task-id goreleaser-retry-publish-auditing --rerun --results ../output/deepswe-survey/survey.jsonl --artifacts ../output/deepswe-survey/runs --timeout-seconds 1800 --tmpfs-mb 4096
```

The recorded attempt also used the existing scoped keep-awake helper. No
held-out tests or solutions were read, no model was called and neither the
dataset pins nor scoring environment changed.

Next: inspect Adaptix's remaining submodule-related setup blocker. Its
recorded submodule is under benchmarks, but that alone does not establish
that the public tests can run without it. No Adaptix run has started.
Numba, KGateway and Pwntools remain parked.
