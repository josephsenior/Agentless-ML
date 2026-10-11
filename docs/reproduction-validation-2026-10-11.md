# Reproduction validation: require test evidence, not just exit 1

The previous controller accepted an ordinary failure exit as reproduction on
the original revision. That could admit a script that never reached its check:
an import or setup error often exits 1 too.

Generated reproduction specifications now require a declared structured report.
There is no legacy exit-only bypass. Reproduction commands cannot restrict their
report to a hand-picked subset of counted IDs.

## The evidence rule

- A baseline is eligible only with a FAIL result, at least one failed test and
  no errored or skipped test cases.
- A candidate reproduction success requires PASS and a nonempty all-passing
  report.
- Missing reports, empty results, errors, skips and contradictions cannot
  qualify as reproduction evidence. Ambiguous ordinary outcomes become harness
  errors; existing timeout/OOM/patch-error statuses are never promoted.
- An unclean sample stops the workflow as infrastructure failure, rather than
  silently changing the sample pool. An unclean candidate is ineligible under
  the existing selection rules.

The rule is enforced when Docker records the execution, when either controller
input mode assesses baseline eligibility, and when the candidate pipeline
collects evidence. Controller baseline artifacts retain both the returned
result and checked result. Docker keeps the original report and records the
status before the additional check. Regression validation is unchanged.

## Standalone Python adapter

`python_reproduction_command("reproduce.py")` creates the trusted command and
CTRF declaration. Its wrapper runs the installed candidate script with its
sibling directory on the import path. A normal completion reports passed,
an uncaught `AssertionError` reports failed, and any other uncaught exception
reports an error. This includes import, syntax and runtime failures, as well
as `sys.exit(0)` or `sys.exit(1)`: an explicit exit is not a successful check.

The wrapper writes its report after execution and preserves the traceback.
It makes no retry or feedback-driven revision. Generated source is executable,
untrusted input and must still run in the existing Docker sandbox. Host tests
execute only controlled, authored fixtures, never model-generated source.

## What this does not prove

Structured reports are not proof of semantic validity. A trusted framework
adapter must classify setup errors correctly; merely naming an arbitrary
failure a test failure is insufficient. An assertion can concern the wrong
behavior, occur during setup, or be intentionally unconditional. Generated
code can catch its own exceptions or tamper with its process. This update
does not make untrusted code honest or prove that an assertion matches the issue.

No generic traceback text matching, source-text heuristic, marker protocol
or multilingual normalization was introduced. Exact-source voting, the frozen
workflow, Docker protections and held-out scoring remain unchanged.

The old V2 recorded Go/JavaScript/TypeScript smoke helper uses exit-only commands
and now fails closed when constructing its reproduction specification. Updating
those trusted reporting adapters is the next implementation task; historical
results remain engineering evidence from the earlier contract, not new results
under this stricter one.

Follow-up: the [multilingual reporting update](multilingual-reproduction-reporting.md)
has now migrated those three commands. The paragraph above records the boundary
at this initial checkpoint; it is no longer a current replay blocker.

## Checks

Focused tests cover clean assertion failure/success, missing reports, mixed
failure/setup errors, skips, import and syntax errors, runtime exceptions,
explicit exits, candidate-source imports, raw report preservation and both
controller baseline modes. Candidate tests verify that an ambiguous pass cannot
produce a prediction. No benchmark suite, live model or held-out tests were run.
The focused validation suite passed 163 tests; nine opt-in live Docker tests
were skipped.
DeepSWE readiness remains 109/113.
