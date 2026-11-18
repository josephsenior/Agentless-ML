# Choosing source context before spending model allowance

**Current implementation:** the [declaration-only index](declaration-index.md)
is now enabled for file localization. This census remains an offline measurement;
the map and extra-inspection scenarios below are not enabled.

This offline census measures the 113 pinned DeepSWE tasks. It does not call a
model, run tests in their repositories or change the live workflow. See the
[per-task table](../experiments/deepswe/source-token-census-2026-11-18/report.md)
and [measurements](../experiments/deepswe/source-token-census-2026-11-18/measurements.json).
Counts use `o200k_base`; provider usage may differ.

All 113 tasks have records. The index prompt has a median of 16,689 tokens,
90th percentile of 121,066 and maximum of 439,004; 92 tasks are at or below
64,000. Adding the complete import map gives a median of 26,541 and maximum
of 1,387,424. The 8k map scenario gives a median of 22,919 and maximum of
446,952. It omits file rows on 49 tasks.

Thirty tasks contain parse errors; three of those also contain unreadable blobs.
Their index counts describe the recognized portion. Seven tasks have Rust
import-analysis limitations. Twenty-three tasks have skeleton rendering errors,
so their inspection payload scenarios are partial. These caveats accompany
the task rows; the distribution is not a guarantee of complete source coverage.

## What the columns mean

The **index prompt** contains the public issue, current file-selection
instructions, source tree and all declarations recognized by the prototype.
This is a reconstructed file-localization input, not the cost of solving a task.
It does not include function bodies.

The **full import map** adds one adjacency row per file with known local imports.
This is a file graph, not a resolved symbol/call graph. Rust imports are not
supported, so small map sizes there do not establish complete graph coverage.
The 1.39M-token map outlier is Yaegi: this rendering repeats same-package
relationships for each file. Grouping package members could substantially reduce
that cost. This census measures the stated representation, not a lower bound
on the size of every possible dependency-map representation.

The **8k map** is a size scenario: keep whole rows in lexical order up to 8,000
map tokens, including an omission notice. The index remains uncapped. This is
not a proposed relevance ranking; the omitted rows may contain needed links.

The **largest-ten skeleton payload** sums standalone token counts for the ten
most expensive skeletons, or all files when fewer exist. These use the existing
adapters' `render_skeleton`: signatures, imports, classes and retained
assignments, with function bodies elided. Large literal initializers can remain.
This is a size scenario, not a prediction of the model's choices. It excludes
the next request's instructions, issue, history and answer. Count the final
assembled prompt again before sending it.

## One fixed inspection phase

A single extra phase is a reasonable variant to discuss with Professor Zhang:

```text
Issue + repository overview
    → model requests one batch of files
    → controller supplies their declarations under a total input budget
    → model makes its final file/symbol selection
    → edit localization → repair → validation → selection
```

The controller fixes the phases. It does not repeatedly ask the model what to
inspect next. This preserves a fixed workflow while changing the information
available during localization, so it should be agreed before fresh evaluation.

Agentless already shows skeletons after file selection. Showing those same
files again would repeat existing behavior. The useful addition would be one
opportunity to reconsider file choices and inspect files outside the original
shortlist. More detail within a shortlist cannot recover a file excluded from it.

A file-count limit alone is insufficient. Effect has an embedded UI assignment
whose standalone skeleton exceeds a million tokens; Drizzle has large dataset
assignments. These inflate the largest-ten scenario without implying that the
model would actually request those files for the given issue.

An inspection phase would need per-file size estimates and a total payload
allowance, followed by a check of the actual assembled request with output
capacity reserved. Oversized choices should be reported or handled by a
pre-agreed rule, rather than silently cutting declarations. The census does not
implement this policy in the live controller.

A bounded import map is simpler but can omit needed relationships. Neither
approach guarantees complete semantic coverage. The
[prototype limitations](source-index-prototype.md), including dynamic dispatch
and project-specific import aliases, still apply.

## Coverage and reproduction

Task IDs come from `experiments/deepswe/corpus_pin.json`. Issue text is read
from its pinned corpus revision. Source comes from each sealed base commit/tree
as regular Git blobs, ignoring working-tree edits and untracked files. Symlinks
and submodule targets are not followed. Existing source/test filters apply.
Gold patches and scoring tests are not read.

Unreadable UTF-8 blobs, parse errors, unsupported Rust import analysis and
skeleton failures are reported explicitly. Affected counts describe the readable,
recognized portion. These caveats do not establish benchmark failures or justify
excluding tasks from the experiment.

```powershell
python tools/survey_source_index_tokens.py --output artifacts/source-token-census-2026-11-18
```

The tool writes one record per task and resumes existing records. Use a fresh
output directory if inputs or policy change. `--retry-blocked` replaces failed
measurement records. Raw records retain exclusions, diagnostics, largest-file
paths and hashes; committed records retain compact measurements and caveats.
