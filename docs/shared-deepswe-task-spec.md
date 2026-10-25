# Shared DeepSWE task records

The exporter packages the public inputs that Agentless-ML and Grinta should
share. It reads the pinned corpus, Git objects at each base commit, existing
environment registrations and saved public baseline reports. It does not start
Docker, download anything, run tests or call a model.

This is the interchange format for the comparison. Neither launcher consumes
it yet. Exporting a record does not mean the comparison is ready to run.

Verified 25 October 2026: all **113 records** exported and their specification
and native-report hashes checked. Rebuilding Actionlint and Numba with identical
inputs produced byte-identical records. The exporter has 12 passing focused
checks; 147 related environment/command checks passed, with four optional
integration checks skipped. The [saved export manifest](../experiments/deepswe/shared_task_export_2026_10_25.json)
contains each record's identity and evidence status. Full bundles remain local
under `artifacts/shared-deepswe-final-2026-10-24/` and can be regenerated.

## Create a bundle

From the repository root:

```powershell
python tools/export_deepswe_task_specs.py `
  --tasks-root ../benchmarks/deepswe/corpus/tasks `
  --repositories ../benchmarks/deepswe/repos `
  --survey ../output/deepswe-survey/survey.jsonl `
  --output artifacts/shared-deepswe
```

The output directory must be new. Add repeated `--task-id` arguments for a
smaller export. Each task gets `task.json` and a byte-for-byte copy of its native
public report. `manifest.json` lists exported records, hashes and any errors.
An inconsistent or missing pin, schedule or baseline is an error, not a partial
task record. Other tasks can still export; the command exits unsuccessfully if
any task fails.

## What each record contains

| Section | Contents |
| --- | --- |
| Identity | Corpus revision, hash of the task's two visible input files, repository URL, full base commit, Git tree and a SHA-256 over its recursive object listing. |
| Problem | The safe loader's problem text, with removal of the trailing branch/commit delivery instruction recorded. |
| Environment | Published and effective image IDs, image user recorded by the baseline, memory/CPU/PID limits, scratch and swap policy, writable paths, offline agent network and registered local hostname mappings. |
| Setup | Registered image profile, reviewed override, exact command exports, setup source hashes, and the special public fixture contracts for Helm, Tomlkit and Wasmi. Dependencies already installed in an image are identified by that image's digest. |
| Public validation | Current command and report contract, plus the historical executed command, complete test inventory, passing IDs, failures, skips and native report hash. |
| Edit contract | Text edits, creation, deletion and renaming; existing permissions preserved. Remaining operation restrictions and Agentless localization rules stay explicit. |
| Timing | Published agent allowance and public-command allowance separately. The agreed total attempt budget is still `null`. |
| Provenance | Exporter's reference revision, exact setup file hashes and corpus pin hash. Grinta's implementation revision remains unresolved until its consumer is implemented. |

The Git tree identifies the starting tracked source, not a hash of a host tar
file. Public configuration is read directly from that tree, so dirty working
files cannot silently change the test plan. Launchers must still materialize
and seal that source, check the image and apply the recorded setup.

The exporter uses the existing safe task loader. It does not open the corpus's
`solution/` or held-out `tests/` directories. Public repository tests and their
saved outcomes are different: both systems are allowed to receive those.

## Historical evidence is not silently upgraded

For example, Actionlint's saved baseline used an earlier Go reporting command.
The exporter retains that command and all its outcomes alongside the current
command. It marks the difference for review. Older records also lack explicit
network or swap fields; those remain missing historical evidence rather than
being filled in from today's defaults.

`current_command_evidence: matching` means the stored command, report contract,
limits and network fields match the exported ones. `review_required` identifies
differences or missing historical fields. Neither label is a new benchmark
readiness classification, and neither proves the two systems have matched
runtimes. The registered 113-task baseline count is unchanged.

Numba's record keeps the 10,800-second public-test allowance. It does not turn
that into an agreed three-hour model attempt. Its saved full inventory remains
9,991 passes, no failures/errors and 618 skipped or expected-failure cases.

For the selected pilot tasks, review the listed differences before reusing a
historical inventory as a frozen selection baseline. This export does not ask
for another corpus-wide test run.

## Integrity and use

`spec_sha256` hashes canonical UTF-8 JSON with that field omitted: sorted keys,
two-space indentation, literal Unicode and one final newline. The native report
has its own SHA-256. `read_record()` in the exporter verifies both when reading
a saved bundle. Identical inputs and provenance produce identical records;
host paths and export timestamps are excluded.

Hashes detect changed inputs, not whether an arbitrary file is trustworthy.
Only consume reviewed bundles produced from the pinned public inputs. Commands
are data during export; a future launcher must explicitly validate its supported
schema, profiles and resource settings before executing them.

Every record has `launch.authorized: false`. Model selection/access, total
budgets, the pilot list, launcher integration and comparison enforcement remain
separate work. The next step is to make both launch paths consume these records
and demonstrate equal initial task and environment settings without model calls.
