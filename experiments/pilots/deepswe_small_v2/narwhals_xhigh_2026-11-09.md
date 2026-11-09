# Narwhals rolling windows: fresh Agentless attempt

Selected task: `narwhals-rolling-window-suite` (Python), with no known prior
repair attempt in the inspected local model-call history and pilot reports.
This is an Agentless-only development attempt; Grinta remains paused.

The previous deterministic ranking is reused, excluding completed Dasel and
Aiomonitor's documented October development exposure. Narwhals is next. The
saved public baseline passed 10,093 cases, with 1,699 skips, in about 106 seconds.
A fresh baseline precedes model calls. This short-baseline selection is a
practical development choice, not a representative benchmark sample.

Settings remain Sol (`gpt-6.1-sol`), xhigh reasoning, one edit-localization
sample, four concurrent repair samples, sequential Docker validation, 2M
once-only content tokens and a two-hour workflow cap. The ten-line repair context
is unchanged. No interface appendix, context fallback or feedback loop is enabled.
The exported selected patch is scored separately by the pinned DeepSWE verifier.

[Selection record](narwhals_xhigh_2026-11-09_selection.json).
Local output: `artifacts/agentless-narwhals-xhigh-2026-11-09`.
## Result

The selected sample zero remains unresolved, with 91/103 issue checks and all
10,093/10,093 regression checks passing. DeepSWE completed normally. This is a
failed task under binary scoring despite substantial issue-check coverage.

All eight model responses completed and all four repairs applied. Each candidate
ran public validation; all reports contained failures. Public report counts
include candidate-added or modified tests and must not be equated to the frozen
regression inventory. Selection considered all four and chose sample zero under
the existing regression/voting rule. No generated patch was manually changed.

Provider-reported usage was 398,537 tokens: 331,885 input and 66,652 output,
including reasoning. The content ledger counted 374,296 tokens. The workflow
recorded about 19.4 minutes; including the separate verifier, the complete
attempt took about 21.3 minutes. Neither cap was reached.

The twelve verifier failures are saved with their native first error messages.
They report missing rolling-method implementations in backend wrappers. This
records what the verifier observed, without claiming a complete root-cause
analysis or a framework defect. No follow-up inference or candidate scoring
was started.

[Result](narwhals_xhigh_2026-11-09/result.json),
[selection and candidate evidence](narwhals_xhigh_2026-11-09/summary.json),
[exported patch](narwhals_xhigh_2026-11-09/selected.patch), and
[native failure summaries](narwhals_xhigh_2026-11-09/issue-failures.json).

## Failure analysis: backend files were never selected

All twelve issue failures stop on a missing backend method, before its numerical
implementation can run:

| Backend | Failed checks | Missing methods |
| --- | ---: | --- |
| DuckDB | 4 | rolling_min (two cases), rolling_max, rolling_median |
| SQLFrame / SparkLike | 4 | rolling_min (two cases), rolling_max, rolling_median |
| Polars eager | 4 | rolling_min, rolling_max, rolling_median, rolling_quantile |

The model selected exactly the allowed five files: public `expr.py` and
`series.py`, `_compliant/expr.py`, `_pandas_like/series.py` and `_arrow/series.py`.
It implemented the public methods and these eager-delegation paths. It did not
select the shared SQL layer or the Polars series wrapper.

For DuckDB and SQLFrame, a public expression records a method name such as
`rolling_min`. Expression evaluation calls that method on the backend expression.
`DuckDBExpr` and `SparkLikeExpr` inherit the shared `SQLExpr`, whose existing
rolling_sum/mean/std/var implementations were not extended. The new methods are
absent, so attribute lookup fails. For eager Polars, the public Series calls its
backend wrapper. That wrapper has neither explicit implementations of the new
methods nor an unrestricted automatic fallback, so attribute lookup fails there
too.

The initial repository tree showed `_sql/expr.py`, `_duckdb/expr.py`,
`_spark_like/expr.py` and `_polars/series.py`. None was selected, none of their
source blocks appeared in symbol, edit or repair prompts, and none was changed
by any of the four candidate patches. Each repair saw the same 7,874-character
prompt from the same localization. This is incomplete file coverage, not
information lost from a correctly selected backend during line-windowing.
Increasing the ten-line window in the five selected files would not add these
unselected files.

The selected patch also added public tests covering eager Polars. Its sixteen
public failures were all in that newly added test file and parametrized for
Polars. The frozen pre-existing regression inventory was preserved. Those
candidate-added failures did not improve the patch through a feedback loop or
change the existing selection rule. The separate verifier then confirmed the
backend omissions with the twelve issue failures above.

The evidence supports incomplete localization and implementation under the
five-file policy. It does not establish a framework defect or prove that the
task is impossible within Agentless-ML. We retain the failed attempt, unchanged
workflow and context window. No manual repair, model request or test rerun was
performed for this inspection.

[Exact prompt checks, path traces and failure grouping](narwhals_xhigh_2026-11-09/failure-analysis.json).

Next, use another fresh task for the next authorized model attempt. More repair
samples from this identical context would still lack these backend source files;
this inspection does not justify changing the agreed workflow.
