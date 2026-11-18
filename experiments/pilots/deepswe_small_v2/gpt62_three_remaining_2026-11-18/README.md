# Three GPT-6.2 Sol xhigh reruns

**Date:** 2026-11-18  
**Provider:** ChatGPT subscription  
**Model:** GPT-6.2 Sol, xhigh reasoning  
**Execution:** Three tasks in parallel; four repair samples per task; one edit sample; up to 10 files with declarations retained; 2,000,000 once-only content-token cap and two-hour task limit. Docker validation was serialized.

| Task | GPT-6.2 issue tests | Existing tests | Outcome | Context tokens | Earlier GPT-6.1 outcome |
|---|---:|---:|---|---:|---|
| etree XML diff patch | 52/52 | 15/15 | Resolved | 86,934 | Resolved, 52/52 and 15/15 |
| Mobly grouped test barriers | 36/79 | 808/808 | Unresolved | 79,510 | Resolved, 79/79 and 808/808 |
| Obsidian scoped ignore markers | 33/33 | 1131/1133 | Unresolved | 106,684 | Resolved, 33/33 and 1133/1133 |

All three runs completed eight model calls and public scoring. The verifier exited successfully. Mobly and Obsidian passed every issue test, but did not qualify as resolved because their selected patches left issue tests failing or regressed existing tests. etree resolved again.

These are independent stochastic runs. The different outcomes do not establish that the model version alone caused a change.

Full prompts, responses, patches, candidate runs, and verifier artifacts remain under the ignored `artifacts/agentless-three-remain-sol62-2026-11-18/` directory. `results.json` records scores, token usage, image digests, and patch hashes.
