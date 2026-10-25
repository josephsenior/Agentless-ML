# Documentation

Start with the [project README](../README.md) for current status and setup.
The guides below describe the implementation we maintain. Earlier investigations
and their original outcomes live in [history](history/README.md).

## Method and implementation

| Question | Guide |
| --- | --- |
| What stays fixed, and how does this differ from Agentless? | [Invariants](agentless-invariants.md), [replication map](replication-map.md) |
| How do the stages connect? | [Fixed workflow](fixed-workflow.md) |
| How are locations and repairs represented? | [Edit localization](edit-localization.md), [repair and selection](repair-selection.md) |
| How are candidate checkouts isolated? | [Workspaces](workspaces.md), [Linux snapshots](git-aware-linux-snapshots-2026-10-04.md) |
| Which tests can affect selection? | [Public validation](public-validation.md), [regression selection](regression-selection.md), [reproduction tests](reproduction-tests.md) |
| What can access the network? | [Network policy](network-policy.md) |

## Languages

- [Python parity](python-parity.md) and [background-error handling](python-background-reproduction.md).
- [Go](go-adapter.md), [JavaScript and TypeScript](javascript-typescript.md), and [Rust](rust-adapter.md).
- [Go/JS/TS reproduction reports](multilingual-reproduction-reporting.md) and [Rust reproduction reports](rust-reproduction-reporting.md).
- [Language engine decision](adr/0003-language-engine.md), following the [original adapter boundary](adr/0002-language-adapter-boundary.md).

## Benchmarks and experiments

| Topic | Current guide |
| --- | --- |
| DeepSWE loading, execution, baseline profiles and scoring | [DeepSWE](deepswe.md) |
| Reproducible small-pilot preparation bundle | [DeepSWE pilot package](deepswe-pilot-package.md) |
| Shared inputs for the Agentless-ML/Grinta comparison | [Shared DeepSWE task records](shared-deepswe-task-spec.md) |
| SWE-bench Pro loading and recorded workflows | [SWE-bench Pro](swe-bench-pro.md) |
| V2 public-suite readiness | [Readiness survey](swe-bench-pro-v2-readiness.md) |
| V2 image and workspace checks | [Batch provisioning](batch-v2-provisioning.md) |
| Review of complete public schedules | [Suite expansion](v2-public-suite-expansion.md) |
| Proposed budgets, eligibility and Grinta comparison | [Experimental configuration](experimental-configuration.md) |
| Shared DeepSWE inputs and restrictions for Grinta | [Capability-matching plan](grinta-capability-match.md) |
| Configurations, small evidence records and raw outputs | [Experiment records](../experiments/README.md) |

The configuration is still a proposal. A baseline count is not a solved-task
count, and saved-response replays are not model results. For the latest Numba
result and registered profile, see the [Numba readiness record](history/deepswe-numba-registered-readiness-2026-10-17.md).

## Development evidence

The [history guide](history/README.md) groups previous environment and test-runner
investigations. Their old readiness counts and next-step statements describe
their own checkpoints, not the current project state.

Some focused guides also retain real-task examples: the
[Rust controller slice](recorded-rust-controller-slice.md),
[issue-derived fd reproduction](fd-issue-derived-reproduction.md),
[Rust reproduction diagnostic](fd-rust-reproduction-diagnostic.md), and
[multiple-sample selection](fd-rust-sample-selection.md).

The [tools guide](../tools/README.md) identifies the commands used for ordinary
work and the helpers retained to reproduce or inspect older evidence.
