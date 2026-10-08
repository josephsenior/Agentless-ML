# Mobly public baseline — 8 October 2026

Mobly now has a usable baseline: **804 passed, two skipped, zero failed**,
with exit code zero. The latest DeepSWE readiness count is **96/113**, leaving
17 tasks needing attention. No latest task records remain in `no_image`.

The only setup needed was pulling the published image and verifying its identity
against the existing corpus pin. Repository sealing and the generic Python
runner succeeded unchanged. The base is
`ec052921917ef201e73cc8e275dc91c5706b345f`, and the verified image is
`sha256:e7f48723e4bf9244cbe5206fdcb204456383c31f43c5a16da98efadda057998f`.

Pytest collected the public repository suite from the unpatched candidate
checkout with `PYTHONPATH=/tmp/work/src:/tmp/work`, ahead of the image's editable
installation. There was no target filter or task-specific override. Networking,
container limits and test expectations were unchanged; no dependency, image,
test or runner changes were made. Held-out benchmark tests and solutions were
not inspected, and no model was called.

The ten warnings remain in stdout. They include an unraisable exception from
an attempted `adb` subprocess that is absent in the image. That warning did not
fail pytest; this passing public inventory does not certify real Android-device
integration. We did not install ADB or suppress the warning.

## Reproduce and evidence

```powershell
.\.venv\Scripts\python.exe tools/survey_deepswe.py `
  --tasks-root ../benchmarks/deepswe/corpus/tasks `
  --repositories ../benchmarks/deepswe/repos `
  --task-id mobly-grouped-test-barriers `
  --rerun --pull `
  --results ../output/deepswe-survey/survey.jsonl `
  --artifacts ../output/deepswe-survey --timeout-seconds 1800
```

The accepted JUnit report, stdout, stderr and execution metadata are under
`../output/deepswe-survey/mobly-grouped-test-barriers/logs/agentless-ml-df9f7400f2bf4e15843122fd125e1450/`.
The survey retry took 22.0 seconds; pytest reports 3.79 seconds. The latest
appended survey record is `ready` with all 806 report IDs accounted for.

Next, retry Boa's old Windows file-lock error. That record refers to the old
editor-visible workspace location; the current survey places candidate
workspaces in the system temporary directory. This is a reason to retry, not
proof that Boa is ready.
