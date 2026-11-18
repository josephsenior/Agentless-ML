# GPT-6.2 Sol xhigh: two previously failing DeepSWE tasks

**Run date:** 2026-11-18  
**Provider:** ChatGPT subscription (`chatgpt-plan`)  
**Model:** GPT-6.2 Sol, xhigh reasoning  
**Workflow:** Agentless-ML only; two tasks ran concurrently; four repair samples per task; one edit sample; up to 10 files; declaration retention enabled; 2,000,000 once-only content-token budget and 2-hour task limit. Docker validation remained serialized.

## Results

| Task | Issue tests (F2P) | Existing tests preserved (P2P) | Result | Context tokens charged |
|---|---:|---:|---|---:|
| Obsidian Linter: automatic table of contents | 0/41 | 1131/1131 | Unresolved | 104,100 |
| Incremental GraphQL delivery | 14/17 | 810/811 | Unresolved | 101,727 |

Both tasks completed all eight model calls and exported a patch. The public verifier completed successfully for both. Neither patch passed all issue tests, so neither task resolved.

## Comparison with the earlier GPT-6.1 Sol xhigh runs

The Obsidian task previously scored 0/41 issue tests and 582/1131 existing tests. This run retained all 1131 existing tests, while still solving none of the 41 issue tests. That is a substantial regression-preservation improvement, but not a task solve.

The earlier GraphQL run scored 14/17 issue tests and 810/811 existing tests. This run has the same test counts and remains unresolved. Its once-only context charge was 101,727 tokens, compared with 108,061 in the earlier run.

These are separate stochastic runs. The score differences do not prove that the model change alone caused the Obsidian improvement.

## Reproducibility references

The full run artifacts, prompts, model responses, patches, per-candidate validation, and verifier outputs are retained under the ignored `artifacts/agentless-obsidian-gql-sol62-2026-11-18/` directory. The run plan records the dataset revision, pinned image digests, model, provider, concurrency, sample count, and budgets. The compact score record is in `results.json` beside this note.
