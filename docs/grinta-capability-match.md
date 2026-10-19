# Matching Agentless-ML and Grinta

Implementation plan, 19 October 2026. The user has chosen the direction:
restrict Grinta's comparison configuration to Agentless-ML's existing repair
capabilities. Do not expand Agentless-ML to match unrestricted Grinta.
This document specifies the work; it does not claim enforcement is implemented.
Model integration, model selection and model budgets are deferred until the
user discusses them with Professor Zhang. No live runs are part of this plan.

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
| Repairs | Agentless-ML's `repair/edits.py` accepts SEARCH/REPLACE edits; `repair/patches.py` rejects file deletion and creates new files as mode 100644. | Restrict Grinta's submitted repairs to the same representable operations. |
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
knowledge. This is a planned interchange format, not a new benchmark or a
replacement for the existing TaskSpec.

| Record section | Required contents |
| --- | --- |
| Identity | Task ID, benchmark revision, visible-input hash, repository URL, resolved base commit and hash of the starting source snapshot. |
| Problem | Same problem text for both arms. Record removal of DeepSWE's branch/commit delivery suffix; submission packaging handles delivery outside either method. |
| Public resources | Repository snapshot, verified public fixtures and their hashes, dependency/cache setup, reviewed command definitions and report formats. Keep reference solutions and hidden grader files out of this record and the agent workspace. |
| Baseline | Existing public baseline evidence and full result inventory, retaining failures and skips. Passing IDs used by Agentless selection remain identifiable. Make equivalent baseline information available to Grinta; prompt presentation may differ. |
| Environment | Published image digest, effective registered image digest, setup identity, working directory, user, environment variables, writable paths, CPU/memory/PID limits, scratch and swap settings, and phase-specific network policy. |
| Edit contract | Allowed regular-text modifications and additions; forbidden deletion, rename, mode/type changes and binary patch operations. Include path and encoding rules verified against the current repair implementation. |
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

## Grinta's restricted comparison configuration

Allow edits to existing regular text files, creation of regular text files,
and multi-file repairs. Preserve existing file modes. Emptying a file is a
content edit, not deleting the file. Rename detection in Git is heuristic:
judge actual path additions/removals and modes, not a similarity label.

Do not add deletion, rename, permission changes, symlink creation, binary edits
or submodule-pointer changes to Agentless-ML. Before claiming exact matching,
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

Use checked edit operations for persistent source changes. Terminal/build/test
execution needs an isolated copy or equivalent boundary so unsupported changes
cannot become the next accepted source state. Inspect changes at that boundary
and again when exporting the patch. A final-patch check alone cannot establish
that an unsupported intermediate state never influenced later observations.
If isolation cannot provide that stronger guarantee, record the limitation
and do not label final-output filtering as full action-level enforcement.
Command-name regexes and instructions to the model are not sufficient.

## Implementation order and completion checks

1. **Export the shared task records.** Reuse existing loaders, registered
   environments and public plans. Resolve real values; reject missing pins or
   unresolved required setup. Check one ordinary development task and one
   registered override without Docker or model calls. Verify determinism and
   absence of answer fields. Then export the remaining records cheaply.
2. **Add Grinta's opt-in comparison profile.** Consume the shared record;
   constrain editing tools and terminal persistence; check the exported patch.
   Exercise allowed edits plus deletion, rename, chmod, symlink, binary and
   indirect shell/script bypass attempts using a small synthetic repository.
   Verify a normal build can still create and remove temporary products.
   Keep restrictions disabled in ordinary Grinta sessions.
3. **Wire the same task setup into both launch paths.** Reuse prepared public
   commands and fixtures. Check runtime installation does not silently replace
   task toolchains or dependencies. Compare effective resource/network settings,
   writable paths and source hashes. Check Pier's concrete environment controls
   before deciding whether any harness change is necessary.
4. **Run one model-free paired rehearsal.** Use recorded Agentless responses
   and scripted Grinta actions on an existing development task. Exercise a
   permitted repair, a forbidden operation and public validation; export both
   final patches. This tests integration, not model quality. Start with a bounded
   public check; expand only if the remaining uncertainty requires it.
5. **Record the demonstrated match and remaining limits.** Save compact
   evidence, implementation revisions, effective task records and configuration.
   No corpus-wide baseline rerun, readiness-count change or benchmark-score
   claim follows automatically from this rehearsal.

The first coding milestone is step 1. Complete the enforcement checks in step 2
before calling Grinta capability-matched. Steps 3 and 4 establish that the
matching profile actually runs in comparable environments.

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
