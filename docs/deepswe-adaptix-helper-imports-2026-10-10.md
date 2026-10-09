# Adaptix: candidate test-helper imports

The corrected official baseline passed: **2,824 passed, 28 skipped, no failures
or collection errors, exit 0**. Readiness remains **104/113**. Adaptix still uses
its original pinned image, not a registered modified environment.

## Why this setup is needed

The public `requirements/test_extra_none.txt` installs `tests/tests_helpers` as
an editable package. In the image that points to `/app`; the streamed candidate
lives under `/tmp/work`. Adding only candidate `src` and root to `PYTHONPATH`
selects candidate Adaptix but does not select this nested helper package. The
[first attempt](deepswe-adaptix-baseline-2026-10-10.md) exposed two import-file
mismatches and therefore exited 1.

The `adaptix-pytest` task override prepends `/tmp/work/tests/tests_helpers` to
the existing candidate source paths. A preflight imports `adaptix`,
`tests_helpers`, `tests_helpers.misc` and `tests_helpers.model_spec`, prints their
actual files, and refuses paths outside their respective candidate package
directories. An import/guard failure exits 125 before pytest, rather than being
accepted as a failed test or a partial passing baseline.

This is a shared test-plan override: the survey, standalone public-test tool and
workflow all load it from `experiments/deepswe/test_overrides.json`. Generic
pytest commands are unchanged. There is no dependency installation or copying
of the image's helper code into the candidate.

## Fresh verification

The live image confirmed all four imports under `/tmp/work`. It then ran the
same default public pytest schedule (`tests`, `examples`), with unchanged
configuration, assertions, report flags and failure-code handling. The helper
files collected without errors; no tests were excluded to obtain the pass.

Base remains `a691069fcadf9131e5f7a5a130a022dc678f3e1d`; image remains
`sha256:528654670f3c591e6491fc6fa01a0b8905bc8dee1b0557c5e76231bcc206f8fe`.
No submodule was fetched or initialized. The same offline Docker runner and
limits were used: read-only root, dropped capabilities, no-new-privileges,
8,192 MiB memory/no extra swap, two CPUs, 2,048 PIDs, 4,096 MiB temporary
storage and 1,800-second cap. Execution took 20.596 seconds; the complete survey
attempt took 23.3 seconds. The owned container was cleaned up.

Host tests: **96 passed, four opt-in delegated-runner checks skipped**. Added
checks cover unchanged pytest flags, custom targets/deadline/report preservation,
successful candidate imports, and rejection of image source or image helpers.

## Test-ID caveat

The skip IDs are exactly unchanged. Seventy-four passing IDs differ between
attempts because public parametrization embeds hexadecimal process addresses;
the other 2,750 passing IDs are identical. Replacing addresses for comparison
only yields the same 2,824 unique passing IDs in each run. Neither saved report
was rewritten and no production ID normalization was added here. The helper
import fix is verified, but stable regression-ID matching across processes
needs a separate assessment before relying on those address-bearing cases.

## Evidence

The official append-only survey is `../output/deepswe-survey/survey.jsonl`.
Raw artifacts are under
`../output/deepswe-survey/runs/adaptix-name-mapping-aliases/logs/agentless-ml-a631aefe3e48498f9cd9c923ec2cb570/`.
The committed [record](../experiments/deepswe/adaptix_helper_imports_2026_10_10.json)
keeps exact pins, counts, verified paths and artifact hashes. The earlier failed
attempt and its evidence remain available as history.
