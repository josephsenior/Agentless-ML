# Reproducibility and provenance

Agentless-ML uses immutable upstream revisions for regression tests and benchmark
integration work. A pin is changed only through a reviewed update that also
regenerates the affected fixtures.

| Component | Pinned revision | How it is used |
|---|---|---|
| [OpenAutoCoder/Agentless](https://github.com/OpenAutoCoder/Agentless) | `b150f28465a77a81a7f4776384957a4271f5bd69` | Published v1.5.0 regression reference |
| [datacurve-ai/deep-swe](https://github.com/datacurve-ai/deep-swe) | `0b9fabbb63b9104d678fe965e1632f2dd9eaa2ea` | Planned benchmark adapter and official harness |
| [scaleapi/SWE-bench_Pro-os](https://github.com/scaleapi/SWE-bench_Pro-os) | `ca10a60a5fcae51e6948ffe1485d4153d421e6c5` | Official evaluation harness and task scripts |
| [ScaleAI/SWE-bench_Pro](https://huggingface.co/datasets/ScaleAI/SWE-bench_Pro) | `7ab5114912baf22bb098818e604c02fe7ad2c11f` | Dataset schema and first answer-free task fixture |
| [qutebrowser/qutebrowser](https://github.com/qutebrowser/qutebrowser) | `ebfe9b7aa0c4ba9d451f993e08955004aaec4345` | Base checkout for the first real Python slice |
| `jefzda/sweap-images:qutebrowser.qutebrowser-qutebrowser__qutebrowser-f91ace96223cac8161c16dd061907e138fe85111-v059c6fdc75567943479b23ebca7c07b5e9a7f` | `sha256:bca2bc90cbe20acca25e9b5e2e96aa751a231a5b6f8f5bc7b7ea3a7b7d449758` | Official environment for the first real Python slice |
| [qutebrowser/qutebrowser](https://github.com/qutebrowser/qutebrowser) | `def864adc8b19bdbc506919270d8ff1408b4faac` | Base checkout for the network-error smoke task |
| `jefzda/sweap-images:qutebrowser.qutebrowser-qutebrowser__qutebrowser-0833b5f6f140d04200ec91605f88704dd18e2970-v059c6fdc75567943479b23ebca7c07b5e9a7f` | `sha256:1607129d3ab3b54033dd9d6fdc9c05c6fad3d36dbdd89f36082f331acfcca35a` | Official environment for the network-error smoke task |
| [qutebrowser/qutebrowser](https://github.com/qutebrowser/qutebrowser) | `df2b817aa418ea7a83c5cbe523aab58ef26a2b20` | Base checkout for the process-error smoke task |
| `jefzda/sweap-images:qutebrowser.qutebrowser-qutebrowser__qutebrowser-0b621cb0ce2b54d3f93d8d41d8ff4257888a87e5-v2ef375ac784985212b1805e1d0431dc8f1b3c` | `sha256:132ceff703ef4ada8d7ca2563b8ebf1bbffe0af6416119d5219374c0dc93e23f` | Official environment for the process-error smoke task |
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
