# Package-level public test schedules — 8 October 2026

## LangChain core

LangChain now has a usable baseline in its pinned published image. Readiness
increases to **94/113**. This is the public core unit schedule, not every partner
or integration suite in the monorepo.

The root-level invocation failed before running tests because the core unit
conftest's custom options were loaded too late. The new `langchain-core-pytest`
override follows `libs/core/Makefile`: start in `libs/core`, name
`tests/unit_tests/` explicitly, clear its five tracing/credential variables,
and retain `-n auto --disable-socket --allow-unix-socket`. Auto workers are capped
at two to match the existing container CPU allocation. The image already
contains the dependencies, so invoking Python directly avoids an unnecessary
UV dependency installation. No dependencies or image contents were changed.

Both `langchain_core` and `langchain_tests` must import from the candidate's
`libs/core` and `libs/standard-tests` directories. A runtime origin check refuses
the image's editable installed source before pytest starts. Package configuration,
markers, snapshots and expected outputs are unchanged. The existing
continue-on-collection-errors policy and JUnit reporting remain in use.

The completed run records **1,664 passing, 21 failed and 33 skipped IDs** out
of 1,718. Pytest's summary distinguishes 1,662 ordinary passes and two xpasses;
the accepted JUnit inventory includes both as passing. The skips include nine
xfails. The remaining URL/SSRF-related failures are visible in the original
report, not excluded or patched. A usable passing inventory is the readiness
criterion; this is not an all-green suite or a repair score.

The pinned image identity is
`sha256:aa019f0c3c7e1677ea820785cc60d32294ca4a9531cfe64066b760672f9f109d`;
the base remains `7cef35bfdebd22148a4c62a10bf01f1fde36e722`.
Evidence is under
`../output/deepswe-survey/langchain-request-coalescing/logs/agentless-ml-d3e370ae38c54271940471fcb6dfcabb/`.
The survey retry took 148.5 seconds; pytest reports 46.01 seconds.

```powershell
.\.venv\Scripts\python.exe tools/survey_deepswe.py `
  --tasks-root ../benchmarks/deepswe/corpus/tasks `
  --repositories ../benchmarks/deepswe/repos `
  --task-id langchain-request-coalescing `
  --rerun --results ../output/deepswe-survey/survey.jsonl `
  --artifacts ../output/deepswe-survey --timeout-seconds 1800
```

The focused execution tests passed 82 cases, with four opt-in Docker checks
skipped. Held-out benchmark tests and solutions were not inspected; no model
was called.
