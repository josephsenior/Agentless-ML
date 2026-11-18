# Clack with GPT-6.2 Sol and GPT-6.1 Sol

GPT-6.2 Sol at xhigh resolved Clack's async autocomplete task on 18 November
2026. GPT-6.1 Sol at xhigh had missed one issue check on the same task.

| Measure | GPT-6.1 Sol | GPT-6.2 Sol |
| --- | ---: | ---: |
| DeepSWE outcome | Unresolved | Resolved |
| Issue checks | 81/82 | 82/82 |
| Verifier regression checks | 643/643 | 643/643 |
| Candidates passing all 640 public checks | 4/4 | 4/4 |
| Processed tokens | 115,361 | 106,927 |
| Once-only context tokens | 61,735 | 61,118 |
| Controller runtime before scoring | 12m 28s | 12m 38s |

Both runs used the declaration index, one edit-localization sample, four
parallel repair samples and sequential public validation, with the same pinned
base commit, image and verifier. The two-hour and two-million context-token
limits were the same. The repeat used a temporary Windows stay-awake request.
The request was released at completion.

The prompts were identical through edit localization. Both models selected the
core autocomplete implementation and public wrappers. They chose different edit
lines, which changed the source excerpts available during repair. In each run,
public validation and the existing tie-break selected the first sample.

The GPT-6.2 patch preserves the previous asynchronous fetch's `AbortController`
after the result arrives. When another search starts, it can still abort that
signal. This passes the check that failed in the GPT-6.1 run. The repeat received
the standard public issue and source inputs. The prior verifier feedback stayed
in the earlier run's record.

GPT-6.2 processed about 7.3% fewer tokens in this run. This is one repeat on a
previously scored task, so broader model choice requires more observations.

[GPT-6.2 record](../experiments/pilots/deepswe_small_v2/clack_declaration_index_sol62_2026-11-18/result.json) ·
[Selected patch](../experiments/pilots/deepswe_small_v2/clack_declaration_index_sol62_2026-11-18/selected.patch) ·
[GPT-6.1 run](clack-declaration-index-run.md)
