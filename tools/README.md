# Tools

The library lives in [`src/agentless_ml/`](../src/agentless_ml/). This directory
contains its command-line entry points, recorded development runs and helpers
used while preparing benchmark environments.

Run commands from the repository root after installing the appropriate extras.
The commands in the first table accept `--help`. Benchmark execution also
requires the pinned public task inputs, source repositories and Docker images
described in the linked guides.

## Main commands

| Command | Purpose |
| --- | --- |
| [demo_fixed_workflow.py](demo_fixed_workflow.py) | Run the small authored example through the recorded controller and export a patch. |
| [demo_public_validation.py](demo_public_validation.py) | Exercise Docker validation and selection on controlled candidates. |
| [run_deepswe_workflow.py](run_deepswe_workflow.py) | Replay a configured DeepSWE development workflow with saved responses. |
| [run_deepswe_tests.py](run_deepswe_tests.py) | Run one DeepSWE task's reviewed public command. |
| [survey_deepswe.py](survey_deepswe.py) | Collect public-baseline evidence across selected DeepSWE tasks. |
| [survey_swe_bench_pro_v2.py](survey_swe_bench_pro_v2.py) | Inventory V2 tasks or execute explicitly selected reviewed plans. |
| [batch_v2_provisioning.py](batch_v2_provisioning.py) | Check image availability and run a small repository/workspace pilot. |
| [provision_v2_pilot_image.py](provision_v2_pilot_image.py) | Inspect or provision one verified image, then run its workspace probe. |
| [score_deepswe.py](score_deepswe.py) | Score a final selected patch with the separate DeepSWE verifier. |
| [score_swe_bench_pro_v2.py](score_swe_bench_pro_v2.py) | Run the local V2 post-selection scorer. |

The two scorers can access held-out verification material. Keep them after
final selection and outside localization, repair generation and public-test
selection. A public test command is not an official benchmark score.

See [DeepSWE](../docs/deepswe.md), [V2 readiness](../docs/swe-bench-pro-v2-readiness.md)
and [batch provisioning](../docs/batch-v2-provisioning.md) for inputs and examples.
There is no live-model benchmark command yet.

## Recorded workflows and selected public checks

The `run_swe_bench_pro_v2_*` entry points retain the Python, Go, JavaScript and
TypeScript development replays. `run_swe_bench_pro_slice.py` also retains the
earlier V1 qutebrowser experiments. The shared
[`run_swe_bench_pro_v2_recorded_slice.py`](run_swe_bench_pro_v2_recorded_slice.py)
contains common replay support.

[`run_recorded_rust_slice.py`](run_recorded_rust_slice.py),
[`run_recorded_python_reproduction.py`](run_recorded_python_reproduction.py),
[`run_fd_path_sort_reproduction.py`](run_fd_path_sort_reproduction.py) and
[`run_fd_exported_regression.py`](run_fd_exported_regression.py) retain the
controller and reproduction checks described in the
[documentation guide](../docs/README.md#development-evidence).

The `run_ansible_*`, `run_element_*`, `run_flipt_*`, `run_navidrome_*`,
`run_openlibrary_*` and `run_teleport_*` scripts run selected public checks on
pinned development tasks. These are repository-coverage checks, not full-suite
plans for all tasks in a repository.

## Fixture and benchmark maintenance

- `capture_agentless_*`: regenerate parity fixtures from the pinned, unchanged
  upstream checkout.
- `capture_prompt_fixtures.py` and `capture_structure_fixtures.py`: maintain the
  prompt and language-structure regression corpus.
- `prepare_deepswe_repositories.py`, `pin_deepswe_images.py` and
  `triage_deepswe_repositories.py`: prepare or inspect pinned benchmark inputs.
- `check_swe_bench_pro_v2_corpus.py`: check the approved V2 corpus projection.
- `build_*` and `verify_*`: reproduce or inspect specific reviewed image/data
  supplements. Their manifests and conditions are recorded under
  [`experiments/`](../experiments/README.md).

Fixture capture requires the revisions in [PROVENANCE.md](../PROVENANCE.md).
Regenerating fixtures is a maintenance operation, not part of ordinary setup.

## Diagnostic helpers

The Numba, Wazero, Pebble, KGateway, Pwntools, Testem and NodeBB diagnostic
families are retained for their tests and historical evidence. They are not
additional Agentless stages. Read the matching
[history record](../docs/history/README.md) before using them.

Some fixed-task scripts execute immediately and do not implement `--help`.
For example, a historical recovery script may target a container that no
longer exists. Do not run every file as a way of discovering what it does.

`run_numba_two_worker_baseline.py` is an explicit one-attempt utility. Its
default cap is 30 minutes; the separately approved three-hour run used
`--timeout-seconds 10800`. That run does not change the shared survey profile.

The subsequently registered Numba task plan now defaults to that verified
three-hour allowance and two-worker command in the regular survey, public-test
tool and workflow. An explicit command-line or experiment timeout overrides
the task default. See the [registration record](../docs/history/deepswe-numba-registered-readiness-2026-10-17.md).

Modules such as `deepswe_environments.py`, `v2_go_public.py`,
`v2_nodebb_public.py`, `pull_deadline.py` and `numba_test_timing.py`, along with
the `.cjs` reporters/services, are support code imported by runners or copied
into containers. They are not all standalone commands. Paths are retained
where tests and recorded instructions rely on them.
