# Pwntools documentation-test diagnostic image

This is a separate environment, not a replacement for the published DeepSWE
image. That image has pytest but lacks Sphinx, the runner named in the public
repository's `TESTING.md`.

The follow-on [native/SSH diagnostic](NATIVE.md) is a different image with its
own dependency changes and results. The Dockerfile described here stays
Sphinx-only.

The Dockerfile adds only the documentation packages needed by the public
Sphinx configuration. It does not run the public machine-install or SSH setup
scripts, create users or keys, install GDB or cross-architecture toolchains,
or enable networking during tests. Failures needing those services remain
visible.

## Build and run

From the framework repository root, with the pinned image already present:

```powershell
$pwntoolsBase = 'sha256:8d726c8e36df1fbee86df7607a3c3b4b441841455b83d806cc2f40533f7976de'
$actual = docker image inspect $pwntoolsBase --format '{{.Id}}'
if ($LASTEXITCODE -ne 0 -or $actual -ne $pwntoolsBase) { throw 'Pinned image unavailable' }
docker tag $pwntoolsBase agentless-ml/pwntools-base:8d726c8e36df
docker build -t agentless-ml/pwntools-docs:2026-10-07 experiments/deepswe/pwntools

.\.venv\Scripts\python.exe tools/run_deepswe_tests.py `
  --tasks-root ../benchmarks/deepswe/corpus/tasks `
  --repositories ../benchmarks/deepswe/repos `
  --task-id pwntools-tube-multiplexing `
  --image agentless-ml/pwntools-docs:2026-10-07 `
  --artifacts ../output/deepswe-survey/pwntools-docs-local `
  --timeout-seconds 1800
```

Use a fresh artifact directory: this tool replaces the task's artifact
subdirectory on each invocation. Do not point it at the canonical survey logs.
The base tag is just a local alias for Docker's build resolver; the original
benchmark tag and image remain unchanged.

The build downloads packages. Test execution still uses the existing runner's
read-only root, no-network setting, 8-GiB memory limit, two CPUs and writable
temporary filesystem. No model is called.

## What is pinned

`requirements.txt` pins all sixteen added documentation packages. The public
requirements allow Sphinx >=8.1.3,<9 and autoprogram <=0.1.5; this environment
uses Sphinx 8.1.3 and autoprogram 0.1.5. The theme and transitive versions are
recorded choices, not a claim that the public project pins those versions.

`dependencies.json` records the observed derived image ID, added versions,
download URLs and wheel SHA-256 hashes from pip's installation report. Existing
runtime package versions were unchanged. Python's virtual-environment bootstrap
does shadow the base pip 25.3 with pip 25.0.1; both are recorded. Neither the
base Python nor the base packages are overwritten. A rebuild may have a
different image ID: retain its own installation report and image ID as evidence.
The Dockerfile also runs `pip check`.

## What the report means

The command follows the public `make -C docs doctest` Sphinx arguments and
loads the candidate's `docs/source/conf.py`. That config registers Pwntools'
platform-aware builder, global setup and cleanup. The observer wraps the base
builder methods that the public custom builder calls; it does not replace
example execution, shared state or comparison flags.

A report case is a **document/group**, not one Python prompt example. A group
passes only if its executed examples pass and its setup and cleanup succeed.
One failed example excludes the entire group from the passing inventory.
Successful setup with no executed tests contributes no passing case. Skipped
and platform-filtered examples are not relabeled as passing cases. This loses
some per-example granularity intentionally, without changing the public suite.

This environment is diagnostic evidence only. Its results are not added to
canonical published-image readiness or used as hidden benchmark scoring.

## Candidate/config check

The opt-in fixture keeps the public configuration but limits discovery to a
synthetic temporary document. It changes a candidate module, checks its new
marker through Sphinx, verifies SKIP/WINDOWS/LINUX filtering, and deliberately
fails a test, setup and cleanup. It is not the full baseline or a benchmark fix.

```powershell
$env:AGENTLESS_PWNTOOLS_DOCS_IMAGE = 'agentless-ml/pwntools-docs:2026-10-07'
$env:AGENTLESS_DELEGATED_TASK_REPOSITORIES = 'C:/Users/GIGABYTE/Desktop/Agentless-ML/benchmarks/deepswe/repos'
$env:AGENTLESS_PWNTOOLS_DOCS_ARTIFACTS = 'C:/Users/GIGABYTE/Desktop/Agentless-ML/output/deepswe-survey/pwntools-probe-local'
.\.venv\Scripts\python.exe -m pytest tests/test_deepswe_pwntools.py -q
```
