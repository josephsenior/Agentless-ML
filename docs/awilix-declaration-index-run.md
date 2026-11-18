# Fresh Awilix task with the declaration index

Agentless-ML ran Awilix's async-initialization task on 18 November 2026, keeping
the configuration used for Clack. The final result is **unresolved**: the selected
patch passed 23 of 24 issue checks and all 162 verifier regression checks.
Clack remains recorded separately as unresolved.

The model was GPT-6.1 Sol at xhigh reasoning, with one edit-localization sample
and four parallel repairs. Public candidate validation ran sequentially under
the shared 8-GiB/two-CPU environment, with networking disabled. Limits remained
two hours and two million once-only context tokens. Grinta was not run.

## Localization and public validation

The declaration index covered 28 source files and 224 declarations, with no
parser or encoding warnings. It contained 2,678 estimated tokens; the complete
file-localization prompt was 3,375 estimated tokens.

The model selected:

```text
src/container.ts
src/resolvers.ts
src/errors.ts
src/awilix.ts
```

These cover container lifecycle, resolver builders, errors and public exports.
Symbol localization included dependency parsing and the relevant builder APIs.
This is useful source-selection coverage, but there was no paired tree-only
control from which to estimate an improvement caused by the index.

The fresh baseline passed 158 public tests. The model excluded none. Three
repair candidates passed all 158. Candidate `loc-0-repair-1` failed public
validation: TypeScript error TS2345 prevented eight suites from running. The
remaining suites reported 49 passing cases; that was not a complete passing
baseline. The candidate was excluded from selection.

The three remaining patches had distinct voting keys. The normal first-appearance
tie-break selected `loc-0-repair-0`. Only that selected patch went to the verifier.

## The remaining scope-isolation failure

| Post-selection verifier | Passed | Total |
| --- | ---: | ---: |
| Issue checks | 23 | 24 |
| Regression checks | 162 | 162 |

The failing check initializes a child scope before initializing its parent.
The expected order is:

```text
scope.initialize()     → scoped service only
parent.initialize()    → parent singleton afterward
```

The generated patch instead starts the parent singleton during the first call.
Its initialization graph iterates `container.registrations`, which includes
inherited registrations. It skips a parent singleton only if it is already
initialized. A still-pending parent singleton therefore enters the child's
initialization schedule.

This identifies the concrete mismatch in the generated initialization logic.
It does not establish a framework defect. The repair excerpt showed the
registration getter delegating to `rollUpRegistrations`, but not that helper's
body; the earlier edit-localization prompt contained the body. The selected
files were relevant, while repair context remained bounded. This run cannot
separate the contribution of omitted context from reasoning or interpretation.

The inspection used verifier material only after final selection and scoring.
No patch modification, alternate-candidate scoring or model retry followed it.
The strict task result remains unresolved.

## Usage and retained evidence

The controller made eight model calls and took 774.8 seconds before export,
about 13 minutes. Post-selection scoring followed separately. Provider usage
was 38,291 input and 87,229 output tokens: **125,520 processed tokens**, including
reasoning in reported output usage. The once-only context budget recorded
52,535 tokens; that is a different accounting measure.

The implementation commit was `e6062ec`. Its run revision has `+dirty` for
pre-existing unrelated edits. Retained source hashes verify that the controller,
declaration index and subscription provider matched their committed versions.

[Compact result](../experiments/pilots/deepswe_small_v2/awilix_declaration_index_2026-11-18/result.json),
[selected patch](../experiments/pilots/deepswe_small_v2/awilix_declaration_index_2026-11-18/selected.patch)
and [post-selection inspection](../experiments/pilots/deepswe_small_v2/awilix_declaration_index_2026-11-18/failure-inspection.json)
are retained. Raw prompts, responses, candidate reports and verifier evidence
remain under `artifacts/agentless-awilix-declaration-index-2026-11-18/`.

Further fresh tasks can use the same condition. These exposed failures should
remain evidence, rather than becoming task-specific changes to the workflow.
