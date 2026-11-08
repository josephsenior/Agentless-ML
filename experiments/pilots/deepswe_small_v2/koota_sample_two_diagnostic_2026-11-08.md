# Koota sample two: saved-patch scoring diagnostic

Sample `loc-0-repair-2` timed out at the existing 1,800-second DeepSWE verifier
limit. The core and React regression reports completed with 137 and 35 passing
cases respectively, with no failures, errors or skips. The issue-specific command
(`vitest run tests/aspect.test.ts`) remained active until timeout and produced no
completed report. Its issue score is unknown; this diagnostic establishes no solve.

This scored the exact saved patch, without editing it or making a model request.
The verifier retained its two CPUs, 8 GiB memory and disabled networking. During
the stall, observed usage was about one CPU core and 200 MiB. That identifies
where the run stopped, but does not establish the offending test or code path.

The earlier public validation had passed 181/181 cases. That public result does
not establish correctness for the issue checks. The scorer reports a timeout with
null counts; the 172 passing regressions above come from native XML copied before
container cleanup. The empty issue report is retained in local artifacts.

The workflow's original selected prediction remains sample zero, with 5/51 issue
checks and 172/172 regressions passing. Sample two was an unselected diagnostic,
so this does not replace the prediction or change the original five-task result.
No additional attempt was started.

Before spending more model allowance on Koota, inspect the saved patch and the
stalled issue-test path. Any selection-policy change should be considered
separately using public validation signals, rather than this held-out outcome.

[Exact record](koota_sample_two_diagnostic_2026-11-08.json),
[saved patch](koota_sample_two_diagnostic_2026-11-08/sample-two.patch),
[core report](koota_sample_two_diagnostic_2026-11-08/base.xml),
[React report](koota_sample_two_diagnostic_2026-11-08/base2.xml), and
[verifier output](koota_sample_two_diagnostic_2026-11-08/container-output.txt).

Local attempt: `artifacts/koota-sample-two-score-2026-11-08`.
