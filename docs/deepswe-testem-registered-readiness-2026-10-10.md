# Testem registration and official readiness refresh

Testem is now **ready** in the official survey. A fresh run through
`survey_deepswe.py` passed the unchanged full public schedule: **497 passed,
three skipped, zero failed**, exit code 0. Test execution took 70.140 seconds;
the survey recorded 76.4 seconds including preparation and cleanup.

Overall readiness is **101/113**, with 12 tasks remaining. This includes
**100 ready in their published pinned images and one ready in an explicitly
registered modified environment**. It is not a claim that 101 published images
work unchanged, or that any repair has solved a benchmark task.

## What registration changes

The new [environment registry](../experiments/deepswe/environments.json) binds
Testem's exact base commit and original published image ID to its verified
four-asset image. The original `corpus_pin.json` is unchanged. The registry
requires the committed passing full-schedule evidence for the exact image and
base; unknown profiles, fields, mutable references and mismatched task pins
are rejected. It contains a reason and an explicit modified-environment label.

The survey, standalone public-test tool and recorded-workflow tool now use
this same registration by default for Testem. Unregistered tasks retain their
published images and commands. Explicit `--image` substitutions remain a
separate diagnostic path and bypass registrations.

The registered runtime reuses the already verified service supervisor and
container runner. It adds only the proven HOME setting and container-local
code.jquery.com mapping, checks all four pinned asset responses, watches the
owned service and preserves the original command's exit code. The full public
globs, Mocha configuration, assertions, report parser and 1,800-second cap are
unchanged. No test filter or diagnostic observer is enabled.

Workflow task artifacts keep the actual image ID; `environment.json` and the
printed summary explain the registration and original pin. Official survey
records carry the same environment provenance and observed protections.
This is public regression infrastructure only: the held-out scorer and its
published benchmark environment have not been changed.

## Fresh official result

Only Testem was rerun; its new result was appended to
`../output/deepswe-survey/survey.jsonl`. Earlier records, including the original
published-image timeout, remain in that file. Latest-record-per-task counting
now gives 101 ready, five unsupported repositories, four harness errors,
two out-of-memory outcomes and one timeout. No readiness rule changed.

Docker inspection confirmed network=none, read-only root, cap-drop=ALL,
no-new-privileges, 8 GiB memory with no extra swap, two CPUs, 2,048 PIDs,
the same 4 GiB executable/nosuid/nodev /tmp, no privileged mode and no published
ports. The owned container was removed and the scoped keep-awake request released.

Raw XML contains 503 nodes: 500 passed and three skipped. Existing duplicate-ID
normalization yields the reported 497/3 across 500 IDs. The
[committed refresh record](../experiments/deepswe/testem_registered_readiness_2026_10_10.json)
keeps the previous and fresh Testem records, corpus status counts, remaining
task list, original/registered image IDs and report digest. Raw artifacts:
`../output/deepswe-survey/runs/testem-per-launcher-reports/logs/agentless-ml-b8158d835b1a40b58c2f28f57a8cc1c5/`.

Reproduce with the project virtual environment and `PYTHONPATH=src`:

```text
python tools/survey_deepswe.py --tasks-root ../benchmarks/deepswe/corpus/tasks --repositories ../benchmarks/deepswe/repos --task-id testem-per-launcher-reports --rerun --results ../output/deepswe-survey/survey.jsonl --artifacts ../output/deepswe-survey/runs --timeout-seconds 1800 --tmpfs-mb 4096
```

The recorded attempt also used the existing scoped Windows keep-awake helper;
no persistent power setting was changed. Before execution, 119 focused checks
passed and four opt-in delegated-runner integration checks were skipped. A
final 33-check registration/Testem subset also passed in the project virtual
environment. These host checks are not benchmark test results.

Next: review registering Cliffy's already verified cache-supplemented image,
then refresh only its official survey result. Nothing has been changed for
Cliffy yet. Numba, KGateway and Pwntools remain parked. No held-out tests or
solutions were read, no model was called, and no further retry has started.
