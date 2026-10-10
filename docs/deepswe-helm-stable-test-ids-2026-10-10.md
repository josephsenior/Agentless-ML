# Stable Helm regression IDs

The two public Helm reports differ in four passing IDs because `TestSave`
builds subtest names from `t.TempDir()`. Both public source files,
`internal/chart/v3/util/save_test.go` and `pkg/chart/v2/util/save_test.go`,
test saving into the temporary directory itself and into its `newdir` child.
The random directory name is not part of what distinguishes those two cases.

The opt-in `helm-save-tempdir-v1` policy replaces only the decimal digits in
these complete IDs:

```text
helm.sh/helm/v4/internal/chart/v3/util::TestSave/outDir=/tmp/TestSave<digits>/001
helm.sh/helm/v4/internal/chart/v3/util::TestSave/outDir=/tmp/TestSave<digits>/001/newdir
helm.sh/helm/v4/pkg/chart/v2/util::TestSave/outDir=/tmp/TestSave<digits>/001
helm.sh/helm/v4/pkg/chart/v2/util::TestSave/outDir=/tmp/TestSave<digits>/001/newdir
```

The stable form uses `TestSave{random}`. Package names, the `001` component,
the `newdir` suffix and outcomes stay distinct. Other packages, test names,
temporary roots, child paths and numeric components are not normalized.

## Where it applies

Only the two Helm task overrides select `helm-go`. That declaration uses the
ordinary Go command script, failure exit codes and raw CTRF path unchanged; its
report metadata opts into the policy. Whole-package discovery, caller targets
and timeout forwarding are unchanged. Survey, standalone validation and workflow
all use the same declaration, so fresh baseline and candidate reports are parsed
with the same rule. Ordinary Go and Go-module reports remain unnormalized.

Normalization happens when parsing a report, not in Helm source or the Go
reporter. Raw reports and old execution records stay unchanged. If distinct raw
IDs in one report would collapse to the same stable ID, parsing fails rather than
silently dropping a case. Exact raw-ID repeats still retain the worst outcome,
as before. The policy is accepted only for CTRF reports.

## Verification

Both [saved baseline reports](deepswe-helm-public-baselines-2026-10-10.md) were
replayed on the host after checking their recorded SHA-256 hashes. Each retains
2,307 IDs and the original 2,239 passed / 58 failed / 10 skipped outcomes.
Exactly four IDs change in each report. All stable IDs and statuses then match
across the two reports, without collisions.

Using the 2,239 passing baseline IDs as the counted regression inventory, the
other normalized report produces zero regressions. Removing one normalized
case or changing its outcome to failed each produces one regression. Unit tests
also check skipped cases, four distinct stable keys, collisions, opt-in scope,
near misses, raw-byte preservation and unchanged command arguments.

Host verification across the report, command, regression-selection, workflow,
Docker-runner and environment tests passed: **276 passed, 13 skipped**. The
skipped cases require opt-in local Docker integration; no full baseline was
needed to check this report-only change.

This was report replay, not a new public-test run or a patched-candidate
experiment. Readiness remains **108/113** and the official survey was not
rewritten. Historical reports should be reparsed with the opted-in policy before
using their IDs; raw dynamic IDs must not be mixed with normalized candidate IDs.

[Replay evidence](../experiments/deepswe/helm_stable_test_ids_2026_10_10.json)
contains the exact raw-to-stable mappings and report hashes.
