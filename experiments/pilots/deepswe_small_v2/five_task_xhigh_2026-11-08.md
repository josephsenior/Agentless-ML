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
