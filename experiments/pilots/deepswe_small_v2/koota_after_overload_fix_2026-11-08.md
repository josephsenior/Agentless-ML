# Koota live follow-up after overload resolution fix

The new run produced three applicable repair candidates and exported
`loc-0-repair-0`. DeepSWE reported 5/51 issue checks and all 172 regression
checks passing. Koota remains unresolved.

The run used Sol xhigh, one edit-localization sample, four parallel repair
samples, the same pinned checkout and Docker image, a 2M content-token cap and
a two-hour limit. All eight requests completed. Provider-reported usage was
137,860 tokens (39,570 input and 98,290 output including reasoning).
The content ledger counted 53,583 tokens. The workflow took about 16.5 minutes,
excluding the initial public baseline.

File localization selected the same five paths as the previous attempt.
Symbol localization selected createWorld, and the fixed resolver provided
world.ts lines 18–408 to edit localization. The resulting repair excerpts
included the subscription hook regions. The earlier attempt had dropped that
entire file at symbol resolution.

Three responses contained applicable edits; one returned no SEARCH/REPLACE
blocks. Candidate 0 failed seven reported public cases, candidate 3 failed
eight, and candidate 2 passed its public report of 181 cases. Candidates 0 and
3 failed cases that their own patches added; all three preserved the frozen
baseline IDs. Their normalized voting keys each had one vote. The deterministic
tie-break selected candidate 0, which was exported and scored. An earlier prose
summary incorrectly identified candidate 2 as the selected patch; the saved
prediction, patch digest and machine-readable record identified candidate 0.
Scoring happened after patch export.

The original five-task batch keeps its 3/5 outcome and its unsuccessful Koota
attempt. This follow-up demonstrates restored context and an exported patch
under the fixed resolver. One fresh stochastic run does not isolate all model
variation or establish a solve-rate improvement from the fix.

[Exact results](koota_after_overload_fix_2026-11-08.json) and
[selected patch](koota_after_overload_fix_selected.patch).
Local prompts, responses and validation evidence are under
`artifacts/agentless-koota-overload-fix-xhigh-2026-11-08`.

## Diagnosis of the 46 failed issue checks

All 46 failed issue checks contain the same Proxy property error. They span
creation, entity operations, queries, modifiers, subscriptions and reset, but
execution stops at the same underlying access.

The generated createAspect wraps a membership trait in a JavaScript Proxy.
The real trait factory defines its schema as non-writable and non-configurable.
The Proxy's get handler returns the aspect's different merged schema object.
JavaScript requires a Proxy to return the target's actual value for a property
with those attributes, so reading schema throws a TypeError.
[ECMAScript Proxy get rules](https://tc39.es/ecma262/multipage/ordinary-and-exotic-objects-behaviours.html#sec-proxy-object-internal-methods-and-internal-slots-get-p-receiver).

A minimal Node reproduction with a locked schema property and the generated
Proxy pattern produced that TypeError. The same error appeared in seven tests
added by the exported patch during public validation. The five passing issue
checks either reject invalid inputs earlier or avoid the failing schema access.
This diagnosis establishes a shared blocking defect in the generated repair;
the rest of the feature cannot be judged from these crashes alone.

The selector ignored candidate-specific added tests when comparing the frozen
baseline IDs. All three candidates preserved those IDs and tied in voting,
so it selected sample 0 by order. Sample 2, whose full public report passed,
was not the scored patch. This is the configured selection policy. Changing
whether candidate-added tests influence selection would be a method decision.

No model request, patch modification or verifier retry was used in this inspection.
