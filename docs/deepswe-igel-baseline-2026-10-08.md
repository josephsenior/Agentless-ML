# Igel public baseline — 8 October 2026

Igel now has a passing baseline: both public tests pass, with exit code 0.
The official survey records `ready`; overall readiness is **98/113**, leaving
15 tasks needing attention.

## Why the original invocation failed

The public test module imports `Igel` before changing the working directory to
`tests/test_igel`. Igel's `configs.py` calculates absolute output paths during
import. Starting pytest at the repository root therefore fixes the model
directory at `/tmp/work/model_results`, while the tests expect it beneath
`/tmp/work/tests/test_igel/model_results`.

The training test looks in the wrong folder. The export test then tries to load
the missing model from that expected folder, producing a downstream ONNX error.
An isolated diagnostic confirmed that changing the initial working directory
alone makes both tests pass.

The checked-in `igel-pytest` override now starts from
`/tmp/work/tests/test_igel` before Python imports Igel. It otherwise keeps the
generic pytest command, candidate-first `PYTHONPATH`, repository configuration,
JUnit reporting and failure exit code. No public tests or application code were
edited, no tests were filtered, and no dependencies or execution limits changed.
The generic Python runner still starts at the repository root for other tasks.

## Official rerun

The sealed base is `bf4544d6c86ab4ace21254cb38a011ce3e845700` and the verified
published image is
`sha256:434ed4187abdb6948dec6434ab4a354d11a19955ebcc706a605ebc6e2470c140`.
The rerun used the existing offline Docker limits: 8-GiB memory, two CPUs,
4-GiB temporary storage and 2,048 PIDs.

Both `tests.test_igel.test_igel::test_fit` and
`tests.test_igel.test_igel::test_export` passed. There were no failures or skips.
Pytest reports 2.78 seconds; the survey completed in 9.5 seconds, including
workspace preparation, execution and cleanup.

```powershell
.\.venv\Scripts\python.exe tools/survey_deepswe.py `
  --tasks-root ../benchmarks/deepswe/corpus/tasks `
  --repositories ../benchmarks/deepswe/repos `
  --task-id igel-persist-feature-schema --rerun `
  --results ../output/deepswe-survey/survey.jsonl `
  --artifacts ../output/deepswe-survey --timeout-seconds 1800
```

The JUnit report, stdout, stderr and execution metadata are under
`../output/deepswe-survey/igel-persist-feature-schema/logs/agentless-ml-0cf1876c2d4c4cf1832486c5fa9a6309/`.
The command regression checks passed: **135 passed, five opt-in tests skipped**
across the execution, adapter and report suites. Held-out tests and solutions
were not inspected, and no model was called.

The remaining tasks with no passing public tests are Eicrud, Numba and Skrub.
Skrub's saved failures are a reasonable next setup review.
