# Small DeepSWE pilot package

The package collects the verified runtime control and the inputs for a proposed
five-task pilot. It contains public task records, their native public baseline
reports, comparison configuration, runtime pins, existing evidence and checksums.
It starts no models, builds no images and runs no benchmark tests.

## Proposed tasks

The proposal chooses one task per language using a fixed hash seed. It excludes
known exposed repositories, supplemented images and public commands longer
than 30 minutes. No model outcomes are used to rank candidates.

| Role | Task | Language | Runtime status |
| --- | --- | --- | --- |
| Engineering control | `actionlint-action-pinning-lint` | Go | Controlled container rehearsal verified |
| Proposed pilot | `aiomonitor-task-snapshots-diff` | Python | Controlled container rehearsal verified |
| Proposed pilot | `pebble-durability-wait-apis` | Go | Controlled container rehearsal verified |
| Proposed pilot | `katex-multicolumn-array-spans` | JavaScript | Controlled container rehearsal verified |
| Proposed pilot | `meriyah-explicit-resource-declarations` | TypeScript | Controlled container rehearsal verified |
| Proposed pilot | `pest-character-class-coalescing` | Rust | Controlled container rehearsal verified |

Actionlint was used for development and earlier model evaluation; it is an
engineering control, not an unseen research task. The five proposed tasks are
not a frozen research subset. The exposure review excludes whole repositories
from the known history. This replaces v1's Testem proposal with KaTeX, the next
JavaScript task under the same hash rule. The Python, Go, TypeScript and Rust
choices are unchanged. The audit covers the named case study, prior trial-folder
identities and recorded Agentless experiments; it is not proof of no other exposure.

The policy and known exposure reasons live in
[`proposal.json`](../experiments/pilots/deepswe_small_v2/proposal.json).
This is a language-coverage proposal for a small pilot, not a statistically
representative sample of the entire benchmark.

The [review](../experiments/pilots/deepswe_small_v2/review.json) and
[runtime evidence](../experiments/pilots/deepswe_small_v2/runtime_verification.json)
retain the five successful checks, original toolchain fingerprints, actual
container observations and source-preflight results. All five passed on 25 October
2026. Docker's initial startup failure and the recovered build-reference error
are recorded in the review as setup interruptions.

## Build and verify

From the Agentless-ML repository root:

```powershell
python tools/package_deepswe_pilot.py build `
  --records-root artifacts/shared-deepswe-final-2026-10-24 `
  --grinta-root ../../Grinta `
  --proposal experiments/pilots/deepswe_small_v2/proposal.json `
  --pilot-runtime-evidence experiments/pilots/deepswe_small_v2/runtime_verification.json `
  --output artifacts/deepswe-small-pilot-v2 `
  --zip artifacts/deepswe-small-pilot-v2.zip

python tools/package_deepswe_pilot.py verify `
  --bundle artifacts/deepswe-small-pilot-v2
```

Output paths must be new. Add `--check-local-image` while Docker is running to
verify the control image is present locally. Without it, the bundle records that
availability was not rechecked; the saved verification evidence is retained.
The ZIP contains configuration and public evidence. Source repositories and
Docker images remain separate inputs identified by their immutable pins.

Identical inputs and implementation provenance produce identical ZIP bytes.
The verifier checks the complete file inventory, file hashes, task/report hashes,
runtime binding and disabled live settings. A changed or extra file is rejected.

## What is pinned

| File | Purpose |
| --- | --- |
| `manifest.json` | Bundle identity, task roles/statuses, implementation revisions and file hashes |
| `tasks/<task-id>/task.json` | Original shared record, including base commit, public command, limits and baseline inventory |
| `tasks/<task-id>/baseline-report.*` | Byte-for-byte native public report, retaining failures and skips |
| `runtime.json` | Per-task verified core-image bindings, including installed Grinta revision |
| `configs/common.json` | Shared settings and outstanding decisions; live execution disabled |
| `configs/agentless-ml.json` | Fixed-workflow contract referencing the common settings and task records |
| `configs/grinta.json` | Adaptive-workflow contract, real Pier factory and opt-in edit guard |
| `configs/mainstream-agent.json` | Explicit placeholder for the additional comparison agent |
| `evidence/container-rehearsal.json` | Existing observed container/toolchain/edit evidence, with setup blockers retained |
| `evidence/pilot-runtimes.json` | Observed checks for the five reviewed tasks, with separate parent and prepared image pins |

The prepared Actionlint image is never assigned to another task. Each task's
image starts from its own pinned parent and receives only the private Grinta
environment, its two entrypoints and parser assets. Task source, global packages
and task build caches are not copied from Actionlint. The installed
Grinta revision inside the verified image is recorded separately from the current
launcher revision; packaging does not silently upgrade installed code.

`tools/verify_deepswe_pilot_runtimes.py` repeats these model-free setup checks.
It checks parent layers, global Python/system packages and available tool binaries
before and after preparation, then loads the language parser offline. Both real
runners execute the same controlled fixture; Pier also exercises Grinta's native
edits, public fixture test and patch export. The five task source checkouts are
verified separately by both launcher preflights. These are runtime checks, not
new full public baselines or five successful repairs. Existing baseline failures
and historical metadata limitations remain in each shared record.

The reused Grinta core is revision `7f8b43a0293c143e2ca6363697baa8185ad3fa34`,
as in the earlier control. Current host launcher revisions are recorded separately.
Model transport remains deferred. Preserve v1 as a historical preparation artifact.

Arm configurations are preparation contracts, not directly executable legacy
Grinta configuration files. The existing model-free rehearsal command remains
the supported way to check the engineering control:
`tools/rehearse_shared_containers.py --help` lists its required paths and pins.
Do not use the historical model defaults as the new research configuration.

## Before a live pilot

**Historical preparation checklist.** Model access and the time/token contract
were subsequently agreed, and a separate shared-container launcher was added.
The first task's engineering attempts and remaining blockers are recorded in the
[29 October checkpoint](../experiments/pilots/deepswe_small_v2/first_task_checkpoint_2026-10-29.md).
The original v2 package below remains a preparation artifact with its original
pins; it is not a record of successful repairs.

Review and freeze the task list and exposure audit, review differences in the
historical public baselines, and select
the model/access arrangement. Aggregate time/token budgets, sample allocation,
retry policy, additional mainstream agent and scoring configuration remain open.
Their fields stay `null` rather than inheriting the earlier draft numbers.

The package is ready to review and reproduce as a preparation artifact. It does
not authorize a live run or change the 113-task public-baseline readiness count.
