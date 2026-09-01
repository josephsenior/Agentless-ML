# Reproducibility and provenance

Agentless-ML uses immutable upstream revisions for regression tests and benchmark
integration work. A pin is changed only through a reviewed update that also
regenerates the affected fixtures.

| Component | Pinned revision | How it is used |
|---|---|---|
| [OpenAutoCoder/Agentless](https://github.com/OpenAutoCoder/Agentless) | `b150f28465a77a81a7f4776384957a4271f5bd69` | Published v1.5.0 regression reference |
| [datacurve-ai/deep-swe](https://github.com/datacurve-ai/deep-swe) | `0b9fabbb63b9104d678fe965e1632f2dd9eaa2ea` | Planned benchmark adapter and official harness |
| [scaleapi/SWE-bench_Pro-os](https://github.com/scaleapi/SWE-bench_Pro-os) | `ca10a60a5fcae51e6948ffe1485d4153d421e6c5` | Planned benchmark adapter and official harness |
| [princeton-nlp/SWE-bench_Lite](https://huggingface.co/datasets/princeton-nlp/SWE-bench_Lite) | `6ec7bb89b9342f664a54a6e0a6ea6501d3437cc2` | Metadata for the Python parity instance |
| [psf/requests](https://github.com/psf/requests) | `091991be0da19de9108dbe5e3752917fea3d7fdc` | Repository fixture for `psf__requests-2317` |

## Golden fixtures

The files under `tests/fixtures/python/` were produced by running the capture
utilities against the pinned checkouts above. Each source-dependent fixture
records a SHA-256 digest of its input. The parity tests compare Agentless-ML with
these captured outputs byte for byte.

To keep the comparison honest:

- the published Agentless checkout is not modified;
- fixture generation uses only the task statement and repository revision;
- gold patches and hidden verifier tests are not copied into the task schema;
- recapturing a fixture must produce the same file before its pin is considered
  reproducible.

## Initial development environment

The first fixtures were captured under Ubuntu on WSL2 with Python 3.11.15, uv,
and Docker 28.5.1. The package test suite is intentionally independent of those
machine-specific checkout paths. Complete experiment runs will record resolved
dependencies, harness revision, container digest, model condition, and resource
limits in their run artifacts.
