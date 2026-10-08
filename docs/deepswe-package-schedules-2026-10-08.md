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

## Drizzle's delegated graph

The `drizzle-turbo` runner uses the public root Turbo graph, not a hand-picked
ORM test file or nine independent commands that skip prerequisites. A dry run
with the pinned Turbo 2.5.3 confirms 27 tasks and all nine test packages:
ORM, kit, seed, zod, typebox, valibot, arktype, the ESLint plugin and integration
tests. Candidate builds and type checks remain prerequisites.

Installed dependencies are copied into writable candidate directories with
their relative workspace links and modes intact. Ownership is not preserved:
some native files have different image UIDs, and the runner keeps CAP_CHOWN
dropped. The root ORM dependency must resolve to the candidate's built `dist`.
The public image's cached pnpm 10.6.3 is selected explicitly and version-checked;
using the image's default pnpm with a new writable home otherwise tries to
download that same package manager again.

Prisma's public generation step initially tried to fetch engine checksums even
though the required binaries are already installed in the pinned image. Its
supported `PRISMA_QUERY_ENGINE_LIBRARY` and `PRISMA_SCHEMA_ENGINE_BINARY`
settings now point to the copied binaries. Both are SHA-256 checked before any
task runs:

- Query engine: `d2208911d61390b094dcb45c1856ff71fec45d8183b7d2e556c849f6a70359c0`.
- Schema engine: `029e6bafee7fe617a3addc4f95c73d7b749fcfd4609e3ecdd75c3c7e643d5271`.

Turbo's loose environment mode forwards these local tool settings to the child
tasks. Networking stays disabled; no host Docker socket, service or credential
is supplied. There is no checksum-ignore setting or substituted image.

The schedule caps concurrent tasks at two, disables remote caching and cache
reads, and adds Vitest's run/JUnit flags through the existing package scripts.
Every package writes the same relative report filename in its own directory;
the merger requires all nine reports and namespaces their IDs. Missing reports
fail closed. The kit script's own TypeScript check and test environment remain
in place.

The first complete build reached seven reports, then seed's failing MySQL
fixtures stopped the root graph: they require `/var/run/docker.sock`, which is
not exposed. Turbo's default fail-fast policy cancelled ORM and integration
tests, so that attempt did not establish readiness. The final runner uses
`--continue=dependencies-successful` to finish unrelated tests, while still
blocking tasks whose build/type prerequisites failed. This changes failure
continuation, not the declared test set or expected outputs. It does not use
`--continue=always` or skip external database tests.

The pinned image remains
`sha256:c83d567eff0ad65e331e26bd3019e128f4fe1c377e3377938e2511e47679ca9b`
at base `e8e6edfef5ca69c6188d320388ad440265911057`.

Verification: the package suite passed 666 tests with 31 optional checks skipped.
After the final command adjustments, execution/adapter/report checks passed
134 tests with five optional checks skipped. These include rejection of
non-candidate LangChain imports, complete nine-package dispatch, preserved
prerequisites and failure on missing reports.
