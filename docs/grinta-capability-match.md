# Matching Agentless-ML and Grinta

Updated 24 October 2026 following Professor Zhang's 23 October reply.
Extend Agentless-ML with file deletion and renaming while keeping its fixed
workflow. This supersedes the 19 October restriction-only plan. The repair
implementation now supports these operations. A 25 October controlled rehearsal
also matched the real container settings and exercised Grinta's edit restrictions.
See the [runtime record](history/shared-container-rehearsal-2026-10-25.md) for
scope; no live model run is part of this work.

Start with a small representative DeepSWE evaluation against Grinta and
mainstream agents, inspect the results, then decide on broader experiments.
SWE-bench Pro V2 follows later; completing all its environments is not a
prerequisite. Zhang prefers a leading OpenAI or Anthropic model, but the exact
model and access arrangement remain unresolved. Model integration stays deferred.

## What we are comparing

Both systems should start with the same task, repository, public resources and
execution conditions. Agentless-ML retains its fixed stages, independent
candidates and deterministic selection. Grinta retains its adaptive sequence
of inspection, edits and public-test feedback. Equal capabilities do not mean
identical prompts, source snippets, test choices or numbers of intermediate
patches. Those differences are part of the methods.

The initial implementation targets DeepSWE. Keep the current Pier integration
while checking whether it can consume the shared setup. A Harbor migration is
not a prerequisite; decide separately if a concrete integration limitation
requires it. Agentless-ML keeps its internal Docker candidate validator.

## What the inspection established

Agentless-ML was inspected at `9039db7ccb3b344fd0b6de1d87cf1ba8a547c400`;
Grinta's local checkout reported `8ae9283eda40154dd16bd466d64c1a44e03ed329`.
This is a source inspection, not a paired execution result or proof that every
local file matches those commits.

| Area | Evidence | Implication |
| --- | --- | --- |
| Task revision | Both DeepSWE pin files name `0b9fabbb63b9104d678fe965e1632f2dd9eaa2ea`. | A shared corpus revision already exists; task content and environments still need per-task equality checks. |
| Repairs (19 October inspection) | Agentless-ML then accepted SEARCH/REPLACE edits and new files, but rejected deletion and renaming. | Superseded by the new explicit deletion/rename operations; check both systems against the updated contract. |
| Context | Agentless-ML's `localization/context.py` filters tests and non-source files from its initial tree. Grinta exposes file-reading and search tools. | Match available public resources, while retaining each method's context-selection behavior. Do not promise identical model-visible context. |
| Shell edits | Grinta's `backend/execution/runtime_mixins/editor_only_shell_policy.py` returns no block under its current compatibility policy. | Editor-tool restrictions alone cannot enforce the comparison condition. |
| Environment | Agentless-ML resolves registered image and runner profiles; Grinta's `evaluation/deepswe/pier_agent.py` installs its runtime through Pier. | Compare effective dependencies and resource settings, not just original image names. |
| Budgets | Grinta's older protocol has an agent timeout multiplier of two. Agentless-ML's research budget document is not enforced. | Neither configuration is the new matched protocol. Do not inherit the multiplier or proposed model limits silently. |

Agentless-ML sources are under `src/agentless_ml/`. Grinta sources above are
repository-relative to its separate checkout. Its other relevant files are
`backend/engine/tools/native_file_tools.py`, `evaluation/deepswe/run_grinta.py`,
`evaluation/deepswe/config.json` and `evaluation/deepswe/protocol.json`.

## Shared DeepSWE task specification

Produce one versioned, machine-readable task record from the existing safe
loader, corpus pin, registered environments and public-test plans. Both launch
paths consume that record rather than maintaining separate copies of setup
knowledge. The [interchange exporter and launcher preflights](shared-deepswe-task-spec.md)
now exist, together with one observed runtime rehearsal. This is not a new benchmark or a
replacement for the existing TaskSpec.

| Record section | Required contents |
| --- | --- |
| Identity | Task ID, benchmark revision, visible-input hash, repository URL, resolved base commit and hash of the starting source snapshot. |
| Problem | Same problem text for both arms. Record removal of DeepSWE's branch/commit delivery suffix; submission packaging handles delivery outside either method. |
| Public resources | Repository snapshot, verified public fixtures and their hashes, dependency/cache setup, reviewed command definitions and report formats. Keep reference solutions and hidden grader files out of this record and the agent workspace. |
| Baseline | Existing public baseline evidence and full result inventory, retaining failures and skips. Passing IDs used by Agentless selection remain identifiable. Make equivalent baseline information available to Grinta; prompt presentation may differ. |
| Environment | Published image digest, effective registered image digest, setup identity, working directory, user, environment variables, writable paths, CPU/memory/PID limits, scratch and swap settings, and phase-specific network policy. |
| Edit contract | Allow regular-text modifications, additions, deletions and explicit renames. Preserve existing permissions; new files use mode 100644. Forbid mode/type changes and binary patches. Include path, destination-collision and encoding rules from the repair implementation. |
| Timing | Reviewed public-command limits separately from the total attempt deadline. An unresolved attempt deadline stays explicitly unresolved and blocks a research launch. |
| Provenance | Specification version/hash, each implementation revision, effective configuration and setup hashes. |

Keep scoring configuration in a separate evaluator record: same pinned verifier
and scoring resources for both exported patches. Do not include hidden test
content in the shared agent input. Model settings belong in a later run
configuration, not in task records generated now.

Reuse the 113 registered baselines as evidence. Do not rerun all of them to
create the specification. Four supplemented-image profiles and Numba's longer
public-command allowance must remain explicit. Numba's 10,800-second command
limit does not automatically grant either arm a three-hour total task budget.

## Grinta's comparison configuration

Allow edits, creation, deletion and renaming of regular text files, including
multi-file repairs. Preserve existing file modes. Emptying a file is a content
edit, not deleting the file. Agentless-ML uses explicit rename instructions;
compare resulting paths, contents and modes rather than Git similarity labels.

Permission changes, symlink creation, binary edits and submodule-pointer changes
remain outside Agentless-ML's repair contract. Before claiming exact matching,
exercise existing executable files, newline/encoding behavior and path rules
against its actual patch exporter; a capability table alone is insufficient.
Grinta must not gain additional operations through its terminal or Git commands.

Apply this only to the new benchmark comparison profile. Preserve ordinary
Grinta sessions and its historical evaluation configurations.

The enforcement must distinguish submitted source changes from temporary build
products. Tests need to create, replace and remove caches and compiled outputs.
Do not ban every filesystem deletion inside a test process. Keep generated
artifacts in disposable execution space where possible; unexpected changes to
submitted source must be detected and rejected, not silently filtered out.

Review the remaining operation limits at command boundaries and at final export.
Deletion and renaming no longer require prohibitions or monitoring for the
comparison. Do not build a filesystem surveillance layer for them. A final-patch
check describes submitted output; it does not prove what every intermediate shell
command did. Document that distinction when defining the remaining restrictions.

## Implementation order and completion checks

1. **Implement deletion and renaming in Agentless-ML.** Keep the fixed stages,
   candidate validation and deterministic selection unchanged. Exercise parsing,
   atomic application, voting and prediction export with recorded responses.
   Completed 24 October: 161 focused checks passed, with five optional
   Docker/compiler checks skipped. The new controller test uses real disposable
   Git workspaces and a local Python check through final prediction export;
   it is controlled implementation evidence, not a live-model benchmark result.
2. **Export the shared task records.** Reuse existing loaders, registered
   environments and public plans. Resolve real values; reject missing pins or
   unresolved required setup. Check one ordinary development task and one
   registered override without Docker or model calls. Verify determinism and
   absence of answer fields. Then export the remaining records cheaply.
   Completed and verified 25 October: all 113 records exported, with native
   public reports retained. Actionlint and Numba exports replay identically.
   Historical command/runtime differences are recorded separately; no baselines
   were rerun and readiness did not change. See the [export guide](shared-deepswe-task-spec.md).
3. **Add Grinta's opt-in comparison profile.** Consume the shared record;
   check the exported patch and review remaining operation restrictions.
   Exercise allowed edits, creation, deletion and renaming, plus rejected
   mode, symlink and binary changes using a small synthetic repository.
   Verify a normal build can still create and remove temporary products.
   Keep restrictions disabled in ordinary Grinta sessions.
   Shared-record preflight consumption is implemented in both launchers.
   Actionlint and Numba have matching prepared source and configured conditions;
   33 focused checks passed across both repositories. This does not complete
   runtime enforcement or establish that Pier's installed runtime is matched.
   The subsequent opt-in completed-action guard and final export check were
   exercised with Grinta's native executor, including Linux mode/type changes.
4. **Wire the same task setup into both launch paths.** Reuse prepared public
   commands and fixtures. Check runtime installation does not silently replace
   task toolchains or dependencies. Compare effective resource/network settings,
   writable paths and source hashes. Check Pier's concrete environment controls
   before deciding whether any harness change is necessary.
   The shared profile now uses real Pier with the same observed protections as
   Agentless. Core installation preserves task tools; the controlled Actionlint
   setup matched. Model transport remains deferred, and this diagnostic image
   is not automatically a registered pilot environment.
5. **Run one model-free paired rehearsal.** Use recorded Agentless responses
   and scripted Grinta actions on an existing development task. Exercise a
   permitted repair, a forbidden operation and public validation; export both
   final patches. This tests integration, not model quality. Start with a bounded
   public check; expand only if the remaining uncertainty requires it.
6. **Record the demonstrated match and remaining limits.** Save compact
   evidence, implementation revisions, effective task records and configuration.
   No corpus-wide baseline rerun, readiness-count change or benchmark-score
   claim follows automatically from this rehearsal.

The verified setup is now packaged with an exposed engineering control and a
proposed five-task language-coverage pilot; see the [package guide](deepswe-pilot-package.md).
The proposal is not frozen, and the five runtime setups remain pending. The
next work is reviewing the pilot list/exposure audit and preparing those exact
runtime bindings. Model/access and budget decisions remain separate.

## Deferred until discussion with Professor Zhang

Do not connect a live model, select a provider/model, calibrate sample counts,
or implement the old proposed token ceilings as an agreed condition now.
Later decisions include reasoning effort, token accounting (including cached
and reasoning tokens), aggregate time, retries, sample allocation and whether
call count should be capped equally. Seventeen fixed-workflow calls do not
automatically imply seventeen adaptive Grinta turns.

Keep provisioning time separate from measured attempt time; account for public
validation inside the eventual attempt budget. The scientific protocol also
needs a frozen eligible subset and development/exposure exclusions, including
tasks used in Grinta's earlier case study. Those decisions precede research
runs, not the model-free implementation work above.
