# Five-task Agentless concurrency pilot

This development batch uses Sol xhigh, one edit-localization sample and four
repair samples per task. Five independent fixed workflows can overlap; each
repair batch can issue four requests. There are at most twenty repair requests
in flight. Public baseline execution, candidate validation and held-out scoring
share one Docker slot. Queue waiting counts toward the two-hour task deadline
except initial baseline preparation. Each task retains a 2M once-only content
token cap. This run does not select a new shared comparison model contract.

The five tasks were chosen before inference. Eligible records had a passing
saved baseline taking at most 120 seconds, an available checkout and local
image, and no known live or recorded repair exposure in the inspected history.
Candidates were sorted by SHA-256 of
`agentless-five-xhigh-2026-11-08:<task_id>`, then the first five were selected:

- etree-xml-diff-patch
- obsidian-linter-scoped-ignore-markers
- koota-composite-trait-aspects
- superjson-error-stack-serialization
- gql-incremental-graphql-delivery

The short-baseline filter is a practical development-pilot choice and does not
establish representativeness. Newly executed baselines still determine whether
the current setup works. Failures remain in the batch results.

Parallel repair generation preserves sample ordering for validation, voting
and tie-breaking. It records and charges every completed in-flight response
even if another request fails. A failed batch stops before validation; there is
no retry or feedback loop. Already-started requests can consume additional
tokens when a limit is reached, and their usage is retained. The default shared
workflow remains sequential unless repair concurrency is explicitly selected.

Run with `tools/run_agentless_batch.py` and the frozen list above. Local output
is `artifacts/agentless-five-xhigh-2026-11-08`. Model calls occur through the
existing subscription connection. Every exported patch is scored after selection.

## Results

The batch solved three of its five tasks with the selected exported patches.
All forty model requests completed; no subscription refusal, local budget
stop, or time-limit stop occurred. Observed Docker execution concurrency was
one. Elapsed time from the frozen plan to the last result was about 22 minutes.

| Task | DeepSWE result | Issue checks | Regression checks | Provider-reported tokens |
| --- | --- | ---: | ---: | ---: |
| Etree XML diff/patch | Resolved | 52/52 | 15/15 | 127,761 |
| Obsidian Linter scoped ignore markers | Resolved | 33/33 | 1,133/1,133 | 184,206 |
| SuperJSON error stack serialization | Resolved | 80/80 | 116/116 | 108,499 |
| GQL incremental GraphQL delivery | Unresolved | 14/17 | 810/811 | 177,405 |
| Koota composite trait aspects | No patch exported | Unscored | Unscored | 90,602 |

Koota returned four explanations without SEARCH/REPLACE edit blocks. All four
candidates applied in each of the other tasks. GQL's candidates failed some
public checks; the selected patch remained unresolved under the separate
verifier. Obsidian's public candidate runs also contained failures, retained in
the evidence, and its selected patch passed all of the verifier's issue and
regression checks. Report-level public counts can differ when the candidate
adds or changes public tests; the frozen baseline IDs still govern selection.

Total provider-reported usage was **688,473 tokens**, averaging about 137,695
per attempted task. All response usage, candidate failures and skips are retained
in the [result record](five_task_xhigh_2026-11-08/results.json). The four exported
patches are beside that file. The Koota attempt remains in the five-task
denominator. This selected development batch does not establish a full
DeepSWE benchmark score or a Grinta comparison.

Four repair samples are sufficient to continue evaluating the workflow at this
stage. More samples would increase usage and would share the same localized
context. This batch does not measure the extra solve rate from increasing the
sample count, so it does not establish that a larger count is worthwhile.

## Koota context-loss inspection

All four repairs received the same selected context and returned explanations
requesting missing implementations. No additional inference was used for this
inspection.

File localization selected entity.ts, query.ts, query-result.ts, world.ts and
index.ts, exhausting the five-file allowance. The tree did show trait.ts,
entity-methods-patch.ts, and modifier.ts, which the model later requested, but
they were not selected and their source was not provided to repair.

A separate reproducible resolver issue dropped world.ts. Symbol localization
returned `function: createWorld`. The TypeScript representation has three
same-name function entries at the pinned revision:

- Line 28 is an overload declaration.
- Line 29 is a second overload declaration.
- Lines 30–408 contain the implementation.

The generic resolver requires exactly one name match. Replaying the selected
name produced empty intervals and an unrecognized location. Therefore
world.ts vanished from the symbol context. Its onAdd, onRemove and onChange
implementations, inside createWorld, never reached edit localization or repair.
The model had selected the correct named function, and its skeleton displayed
the overloads. This demonstrates a framework limitation in resolving an
overload group. A deterministic resolution rule for a verified overload group
with one implementation could address that context loss while keeping genuine
same-name ambiguity handling.

Edit localization further narrowed the remaining files. query.ts went from
443 displayed coarse-context lines to 176 fine-context lines, and
query-result.ts from 283 to 225. entity.ts supplied the creation entry point
but not the trait operations it calls. The four repair responses identified
these missing implementations and declined to invent applicable SEARCH blocks.

This identifies both a specific resolver issue and broader file/context
selection limits on this attempt. Correcting overload resolution alone does
not establish that Koota would be solved: the trait and modifier files would
still be absent from the selected set. No code correction, retry, or held-out
inspection was performed during this diagnosis.

## Overload resolution fix

The implementation now groups adjacent TypeScript overload signatures with
their implementation in the same syntax scope when resolving a model-selected
name. The interval includes the signatures and implementation. Functions,
methods and constructors are covered. Static/instance mismatches and genuine
duplicate implementations remain ambiguous. Source representations and prompt
skeletons retain all original declarations.

An offline replay of Koota's unchanged saved symbol response restored
`packages/core/src/world/world.ts` lines 18–408, covering all three subscription
hooks. Trait and entity-method files still depend on file localization selecting
them in a future run. The original pilot attempt remains unsuccessful.

The regression checks covered overload syntax, comments between declarations,
qualified class members, constructors, distinct scopes, duplicate implementations,
accessors and declaration-only signatures. The adapter, structure corpus,
prompt fixtures and recorded workflow checks passed (110 passed, two optional
Node execution checks skipped).
[Replay evidence](koota_overload_resolution_2026-11-08.json).
