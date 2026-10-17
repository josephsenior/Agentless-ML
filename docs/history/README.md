# Development history

These notes retain earlier investigations, decisions and execution evidence.
Readiness counts, environment settings and proposed next steps belong to the
date or run described in each note. Start with the
[current documentation](../README.md) when deciding what to run today.

The notes keep their original filenames. Their text and links remain useful
for tracing why a runner or environment profile was introduced; moving them
here does not change the recorded test outcomes.

## Useful starting points

| Investigation | Records |
| --- | --- |
| DeepSWE survey and runner setup | [Integration checkpoints](deepswe-integration-log.md), [initial survey](deepswe-survey-2026-09-28.md), [runner review](deepswe-runner-review-2026-10-04.md), [scratch and swap](deepswe-scratch-swap-2026-10-12.md) |
| Numba runtime | [Earlier full attempts](deepswe-numba-full-attempt-2026-10-08.md), [compilation diagnostic](deepswe-numba-compilation-diagnostic-2026-10-13.md), [completed three-hour attempt](deepswe-numba-three-hour-attempt-2026-10-17.md) |
| Wazero and KGateway resources | [Wazero memory](wazero-memory-diagnostic-2026-10-05.md), [short diagnostic](wazero-short-diagnostic-2026-10-11.md), [KGateway disk scratch](deepswe-kgateway-8gib-tmpfs-full-2026-10-12.md) |
| Stable public test IDs | [Adaptix](deepswe-adaptix-stable-ids-2026-10-10.md), [Helm](deepswe-helm-stable-test-ids-2026-10-10.md), [Pebble parent matching](deepswe-pebble-parent-matching-2026-10-11.md) |
| Supplemented images | [Cliffy](deepswe-cliffy-registered-readiness-2026-10-10.md), [GoReleaser](deepswe-goreleaser-registered-readiness-2026-10-10.md), [Testem](deepswe-testem-registered-readiness-2026-10-10.md), [Pwntools offline data](deepswe-pwntools-offline-2026-10-08.md) |
| Public fixture setup | [Tomlkit](deepswe-tomlkit-public-fixtures-2026-10-10.md), [Wasmi](deepswe-wasmi-public-fixtures-2026-10-10.md), [Helm](deepswe-helm-container-fixtures-2026-10-10.md) |
| NodeBB, now parked | [Complete diagnostic](nodebb-no-bail-diagnostic.md), [remaining baseline failures](nodebb-additional-baseline-failures.md), [writable dependencies](nodebb-writable-dependencies.md) |
| V2 repository pilot | [Provisioning and public-check log](v2-provisioning-log.md), including Teleport and Proton Mail transfer evidence |
| Multilingual reproduction replays | [Recorded replay](multilingual-reproduction-replay-2026-10-11.md) |

Other notes in this directory cover the individual repositories and intermediate
checks behind those results. The compact machine-readable evidence stays under
[`experiments/`](../../experiments/README.md); raw local artifacts stay at the
paths cited by those records.

Do not treat a historical command as the current execution plan. In particular,
some diagnostics use explicitly different images, network conditions or test
scopes. Current profile registration is described in the benchmark guides.
