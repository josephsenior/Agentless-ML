# Proposed experiment configuration

The implementation is far enough along to write down the condition we intend
to compare. The [machine-readable draft](../experiments/research_protocol_draft.json)
separates current behavior from proposed budgets and decisions that still need
review with Professor Zhang. It is not loaded by the controller, and its budget
limits are not yet enforced. Nothing in this draft launches a model run.

## The method we would report

Call the condition **Agentless-ML, generalized fixed workflow**. The controller
owns localization, sampling, validation and final selection. Models provide
stage responses; candidate test output does not trigger a new model trajectory.

The current method differs from the pinned Agentless v1.5.0 reference in several
ways that affect capabilities or selection:

| Choice | Implemented behavior | Reason to declare it |
| --- | --- | --- |
| Repair scope | Apply valid edits atomically across multiple files; allow new regular text files. No deletion, rename or mode changes. | Broader than the reference postprocessor's first-file behavior; file creation also changes the prompt. |
| Patch voting | Python uses AST-based normalization with documented exceptions. Other languages use comment-stripped textual diffs. | Formatting variants can form different voting groups; neither key proves semantic equivalence. |
| Reproduction selection | Check every parseable sample on the base, vote by exact extracted source among eligible failures, break ties by first appearance, then freeze one source. | Differs from upstream Python normalization and printed-marker checks. |
| Reproduction evidence | Require structured reports and a clean assertion/test failure on the base; passing, errored or skipped evidence cannot qualify. | Stronger evidence contract, with language-specific limitations documented in the reporting notes. |
| Regression selection | Protect passing base IDs after a frozen exclusion response; unknown exclusions fail rather than being ignored. | Changes some upstream error and empty-schedule behavior. |
| Infrastructure outcomes | Candidate timeout/OOM/harness errors make it ineligible; reproduction-baseline infrastructure errors stop the run. | Differs from counting all such cases as ordinary failed tests. |
| Candidate ranking | Minimum regression failures, prefer reproduction passes if present, normalized-patch majority, first appearance. | Preserves the intended fixed ranking order. |

Build-breaking patches remain a distinct case: where a trusted runner identifies
one, it counts as failing every counted regression test. A build failure is not
automatically interchangeable with a Docker error. See the
[replication map](replication-map.md), [repair rules](repair-selection.md),
[regression selection](regression-selection.md) and [reproduction rules](reproduction-tests.md).

## Proposed starting budgets

Model integration and budget choices are deferred pending the user's discussion
with Professor Zhang. The numbers below are retained as earlier proposals,
not instructions to implement them now. Current model-free work follows the
[capability-matching plan](grinta-capability-match.md).

For engineering calibration, propose one file response, one symbol response,
two edit-location samples, four repairs per edit sample, four reproduction
samples and one regression-exclusion response: at most **17 model calls**.
Malformed responses consume their allocation; there is no resampling.

Proposed common ceilings are 200,000 input tokens and 40,000 output tokens per
task, with at most 32,000 input and 4,096 output tokens per call. These are
starting values to review after measuring real runs, not values derived from
the existing recorded fixtures or a claim of upstream budget parity. The same
aggregate ceilings would apply to Grinta, while its adaptive loop decides how
to use its calls. Reasoning-token accounting must be resolved with the chosen
provider before these ceilings can be compared fairly.

The proposed task clock covers generation and validation, while environment
provisioning is measured separately. Each command receives the smaller of its
reviewed cap and the task time remaining. Existing runners enforce individual
command limits; they do not yet enforce this complete research budget.
Choose the exact model/revision, temperatures and seeds before implementation
is treated as an experimental condition.

## Task eligibility and comparison

Network policy is phase-specific, not synonymous with Agentless tool access.
See the [policy review](network-policy.md): V2 keeps the agent phase offline
but permits normal setup/verifier networking. Connected unchanged-base
diagnostics must not silently supply selection baselines for offline candidate
runs. Matching selection conditions still need to be agreed; no network-enabled
candidate condition is introduced by this review.

Freeze the eligible task list before looking at model outcomes. Require a
pinned base/image, a sealed repository, a reviewed complete public schedule
and a baseline passing-test inventory. Existing baseline failures remain
visible; they do not automatically exclude a task. Syntax-only checks do not
satisfy this proposed research eligibility rule.

The latest registered DeepSWE survey has 113 usable public baselines. Numba
also completed a [cache-corrected three-hour baseline](history/deepswe-numba-writable-cache-2026-10-17.md)
with 9,991 passes, no failures/errors, and 618 skipped or expected failures.
Host execution took about 94 minutes; the native runner reported about 99.
Its [longer public-validation profile is registered](history/deepswe-numba-registered-readiness-2026-10-17.md)
for baseline and candidate commands. It still does not fit the original
30-minute public-command condition. That runtime also
needs to be accounted for before assuming multiple candidates fit the task clock.

Testem, Cliffy, GoReleaser and Pwntools use registered modified images. Report
that stratum explicitly and give both systems the same registered setup.
A task becoming eligible later belongs to a new frozen task-list version,
not a quiet change to a running experiment.

V2 has 642 safely loaded tasks and four reviewed development smoke plans.
The [repository pilot](batch-v2-provisioning.md#current-coverage-17-october-2026)
also has workspace evidence for selected tasks from nine repositories.
Complete public schedules and sealed sources still need review for additional
experiment tasks. The existing selected tests and syntax checks remain
engineering evidence, rather than full-suite eligibility.

The complete-public-schedule requirement above is a proposed research choice.
A pilot can use a fixed eligible subset; preparing every task in both corpora
is not a prerequisite for that pilot. Its subset and limits must be declared
before inspecting model outcomes.

Development tasks and tasks whose reference solutions were used to validate
the scorer need an explicit exposure list before selecting a research holdout.
That list is still open; excluding just the four V2 smoke tasks would be
insufficient. Do not describe existing hand-written repair fixtures as an
unseen model evaluation.

For Grinta, match task versions, initial repository content, model revision,
public information, edit-operation capabilities, environment and aggregate
budgets. Adaptive tools and feedback remain its intended difference. Source
inspection has begun; runtime matching is not yet validated. The agreed
implementation direction is to restrict Grinta to Agentless-ML's existing
repair operations, not expand Agentless-ML. The
[shared task specification and implementation plan](grinta-capability-match.md)
records the inspected gaps, enforcement requirements and model-free milestones.

Each condition exports one final patch. Score it afterwards with the same
pinned verifier and resource policy. Keep the original eligible denominator
and report unresolved runs and system failures separately rather than dropping
them. Local V2 verifier smoke evidence does not replace official Harbor replay
when claiming an official V2 result.

## Work before freezing

1. Choose the initial task set and review complete V2 public schedules for those
   tasks, expanding by repository as needed. The four reviewed smoke
   plans now pass with sealed sources in the [fresh Docker survey](swe-bench-pro-v2-readiness.md#completed-offline-replay);
   they still do not satisfy the proposed full-suite eligibility rule.
2. Agree the declared method and comparison requirements with Professor Zhang.
3. Select a model, implement complete budget accounting, and calibrate the
   proposed sample counts on development tasks.
4. Pin the holdout, exposure list, environment strata, seeds and scoring route;
   verify the matched Grinta condition before starting research runs.

Keep the draft marked unapproved until these decisions are recorded. Changing
a number in a JSON document does not make the runtime enforce it.
