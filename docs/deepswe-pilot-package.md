# Small DeepSWE pilot package

The package collects the verified runtime control and the inputs for a proposed
five-task pilot. It contains public task records, their native public baseline
reports, comparison configuration, runtime pins, existing evidence and checksums.
It starts no models, builds no images and runs no benchmark tests.

## Proposed tasks

The proposal chooses one task per language using a fixed hash seed. It excludes
the known task-level exposures, supplemented images and public commands longer
than 30 minutes. No model outcomes are used to rank candidates.

| Role | Task | Language | Runtime status |
| --- | --- | --- | --- |
| Engineering control | `actionlint-action-pinning-lint` | Go | Controlled container rehearsal verified |
| Proposed pilot | `aiomonitor-task-snapshots-diff` | Python | Pending |
| Proposed pilot | `pebble-durability-wait-apis` | Go | Pending |
| Proposed pilot | `testem-bail-on-test-failure` | JavaScript | Pending |
| Proposed pilot | `meriyah-explicit-resource-declarations` | TypeScript | Pending |
| Proposed pilot | `pest-character-class-coalescing` | Rust | Pending |

Actionlint was used for development and earlier model evaluation; it is an
engineering control, not an unseen research task. The five proposed tasks are
not a frozen research subset. The known exposure list is incomplete and excludes
task IDs, not whole repositories. For example, the proposed Testem task shares
a repository with an earlier study task. Review these overlaps before freezing
selection or making claims about unseen tasks.

The policy and known exposure reasons live in
[`proposal.json`](../experiments/pilots/deepswe_small_v1/proposal.json).
This is a language-coverage proposal for a small pilot, not a statistically
representative sample of the entire benchmark.

## Build and verify

From the Agentless-ML repository root:

```powershell
python tools/package_deepswe_pilot.py build `
  --records-root artifacts/shared-deepswe-final-2026-10-24 `
  --grinta-root ../../Grinta `
  --output artifacts/deepswe-small-pilot-v1 `
  --zip artifacts/deepswe-small-pilot-v1.zip

python tools/package_deepswe_pilot.py verify `
  --bundle artifacts/deepswe-small-pilot-v1
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
| `runtime.json` | Verified core-image binding for Actionlint only, including installed Grinta revision |
| `configs/common.json` | Shared settings and outstanding decisions; live execution disabled |
| `configs/agentless-ml.json` | Fixed-workflow contract referencing the common settings and task records |
| `configs/grinta.json` | Adaptive-workflow contract, real Pier factory and opt-in edit guard |
| `configs/mainstream-agent.json` | Explicit placeholder for the additional comparison agent |
| `evidence/container-rehearsal.json` | Existing observed container/toolchain/edit evidence, with setup blockers retained |

The prepared Actionlint core image is never assigned to another task. Those
tasks need their own prepared runtime images and observed checks. The installed
Grinta revision inside the verified image is recorded separately from the current
launcher revision; packaging does not silently upgrade installed code.

Arm configurations are preparation contracts, not directly executable legacy
Grinta configuration files. The existing model-free rehearsal command remains
the supported way to check the engineering control:
`tools/rehearse_shared_containers.py --help` lists its required paths and pins.
Do not use the historical model defaults as the new research configuration.

## Before a live pilot

Review and freeze the task list and exposure audit, prepare and verify the five
runtime setups, review differences in the historical public baselines, and select
the model/access arrangement. Aggregate time/token budgets, sample allocation,
retry policy, additional mainstream agent and scoring configuration remain open.
Their fields stay `null` rather than inheriting the earlier draft numbers.

The package is ready to review and reproduce as a preparation artifact. It does
not authorize a live run or change the 113-task public-baseline readiness count.
