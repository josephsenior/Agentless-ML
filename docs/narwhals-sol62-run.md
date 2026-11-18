# Narwhals rolling windows with GPT-6.2 Sol

GPT-6.2 Sol at xhigh resolved the DeepSWE Narwhals rolling-window task.
The verifier reported 103/103 issue checks and 10,093/10,093 regression checks.
All four repair candidates preserved the 10,093 tracked public tests.

| Measure | Earlier GPT-6.1 Sol xhigh | GPT-6.2 Sol xhigh |
| --- | ---: | ---: |
| Issue checks | 91/103 | 103/103 |
| Verifier regression checks | 10,093/10,093 | 10,093/10,093 |
| Processed tokens | 398,537 | 493,267 |
| Controller runtime before scoring | 19m 25s | 18m 37s |

The earlier run selected five files and missed `narwhals/_sql/expr.py` and
`narwhals/_polars/series.py`. The new run selected ten files, included both in
the repair prompt, and edited both in the selected patch. The model and the
localization configuration changed together. The repeat used the current
declaration index, ten-file limit and declaration retention. This result
cannot isolate the contribution of any one change.

Regression selection used 214,095 input tokens. Edit localization used 121,829
and file localization used 59,953. Each of the four repair requests used
3,804 input tokens. The controller preserved all baseline-passing tests in
the regression set, and the baseline report retained 1,699 skips.

[Run record](../experiments/pilots/deepswe_small_v2/narwhals_declaration_index_sol62_2026-11-18/result.json) ·
[Selected patch](../experiments/pilots/deepswe_small_v2/narwhals_declaration_index_sol62_2026-11-18/selected.patch) ·
[Earlier result](../experiments/pilots/deepswe_small_v2/narwhals_xhigh_2026-11-09/result.json)
