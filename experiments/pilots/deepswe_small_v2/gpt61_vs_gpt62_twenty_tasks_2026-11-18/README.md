# GPT-6.1 vs GPT-6.2 on the 20-task DeepSWE set

**Comparison date:** 2026-11-18  
**Reasoning:** xhigh for the paired recent runs.  
**Task sampling:** one edit-localization sample and four repair samples per scored run.  
**Important:** these are separate model generations, not identical outputs replayed under a controlled model-only experiment. Agentless code revisions changed between runs, and some GPT-6.1 runs used older file-selection limits. Treat the results as observed task outcomes, not proof that a model version alone caused a difference.

## Per-task results

F2P is the benchmark's issue-test count. P2P is the count of existing tests preserved. “No candidate” means the workflow could not export a repair patch. “Unreported” means the verifier did not find the issue test IDs in its test report; the 0 score must not be read as proof that the model's implementation failed those individual tests.

| Task | GPT-6.1 | GPT-6.2 | Readout |
|---|---|---|---|
| Awilix async container initialization | 23/24 F2P, 162/162 P2P, unresolved | 24/24, 162/162, resolved | 6.2 resolved it |
| Clack async autocomplete options | 81/82, 643/643, unresolved | 82/82, 643/643, resolved | 6.2 resolved it |
| Dasel HTML document format | 0/146, 406/1012 | 0/146, 1012/1012 | 6.2 preserved existing tests, but its patch only added the HTML parser import; the new parser did not build, so it did not solve the task |
| DynamoDB Toolbox conditional attribute requirements | No patch candidate | No patch candidate | Neither run produced a scoreable patch |
| Kysely window grouping helpers | No patch candidate | 0/254, 0/22, unresolved | The saved patch did not compile. A separate clean run passed all 22 regression tests. |
| Mobly grouped test barriers | 79/79, 808/808, resolved | 36/79, 808/808, unresolved | 6.1 was better |
| Obsidian link format conversion | 0/60, 1131/1131 | 0/60, 582/1131 | 6.1 preserved more tests; 6.2 did not solve the issue |
| Obsidian automatic table of contents | 0/41, 582/1131 | 0/41, 1131/1131 | 6.2 preserved existing tests, but its patch broke the expected `RuleBuilderClass.getRule` API and the issue suite could not start |
| etree XML diff patch | 52/52, 15/15, resolved | 52/52, 15/15, resolved | Same result |
| Obsidian scoped ignore markers | 33/33, 1133/1133, resolved | 33/33, 1131/1133, unresolved | 6.1 was better; 6.2 regressed two existing tests |
| Koota composite trait aspects | 5/51, 172/172 | 35/51, 172/172 | 6.2 made substantial issue-test progress; neither resolved it |
| SuperJSON error stack serialization | 80/80, 116/116, resolved | Initially no response on two attempts; a later GPT-6.2 run scored 80/80, 116/116, resolved | The completed 6.2 run resolved the task; see the follow-up run record below |
| Incremental GraphQL delivery | 14/17, 810/811 | 14/17, 810/811 | Same result |
| Geo ShapeIndex serialization | 0/24, 532/599 | 22/24, 599/599 | 6.2 was clearly better, but still missed two issue checks |
| HTTPX deterministic cookie store | Timed out after 6/8 model responses; no score | 115/115, 1281/1281, resolved | 6.2 completed a solve; 6.1 has no scored result to compare |
| Narwhals rolling window suite | 91/103, 10093/10093 | 103/103, 10093/10093, resolved | 6.2 resolved it |
| Koota pair relation tracking | No patch candidate in the earlier runs | 34/38, 172/172 | 6.2 produced a useful partial patch |
| ts-pattern matchEach | 0/85, 6/6 | 0/85, 6/6 | Same unresolved result; the 6.2 patch failed TypeScript checking in `match-each.test.ts` |
| Vulture persistent analysis cache | 24/24, 294/295 | 24/24, 290/295 | 6.1 preserved four more existing tests |
| KaTeX multicolumn array spans | 84/94, 599/599 | 0/94, 0/599 | 6.1 was better; the 6.2 patch broke test-suite loading |

## Overall comparison

GPT-6.2 had better measured results on eight tasks: Awilix, Clack, Dasel's existing-test preservation, Geo, Koota composite, Koota pair, Narwhals, and Obsidian automatic ToC's existing-test preservation. HTTPX also resolved under 6.2 after the 6.1 run timed out, though that is not a score-for-score pair.

GPT-6.1 had better results on five tasks: Mobly, Obsidian link conversion, Obsidian scoped ignore markers, Vulture, and KaTeX. Four tasks had the same score or same no-patch outcome: etree, GraphQL, ts-pattern, and DynamoDB. Neither model resolved Kysely. GPT-6.1 exported no patch and the GPT-6.2 patch failed to compile. SuperJSON now has valid resolved results for both models after one successful 6.2 run.

This does **not** establish that GPT-6.2 is generally superior. The 6.2 runs solved Awilix, Clack, and Narwhals where the earlier runs missed one or more issue tests, and made strong partial progress on Geo and Koota. But the 6.1 run solved Mobly and Obsidian scoped ignore where the 6.2 selected patches failed, and 6.1 produced a much stronger KaTeX result. The outcomes depend on the generated patch and selection for that particular run. SuperJSON is now resolved on both model versions.

## Why some GPT-6.2 results failed, and what can be fixed

### Generated-patch mistakes

These are concrete code defects in the selected model patches. They can be corrected by generating a better candidate. Editing the patch by hand and counting it as the model's benchmark result would invalidate the comparison.

- **Mobly:** the patch calls `_exec_one_test`, but the repository method is `exec_one_test`. That nonexistent method caused 43 issue tests to fail. This is a patch-level naming mistake.
- **Obsidian scoped ignore:** temporary `obsidian-linter-protected-line-*` comments escaped restoration in two existing tests. The expected `{CUSTOM_IGNORE_PLACEHOLDER}` values were left replaced by those comments. This is a patch-level restoration bug.
- **Obsidian link conversion:** the patch imports `../rule` from `src/rules/link-style.ts`, but that module does not exist. Three test suites, including the new link-style suite, could not load. This is a patch-level import-path mistake.
- **KaTeX:** the patch calls a function-registration API that is not available in the form used; test startup fails with `defineFunction is not a function`. This is a patch-level API integration mistake.
- **GraphQL:** three issue tests fail around assigning the read-only `directives_ast` property; one existing test also expects unsupported transports to raise but they do not. These are patch-level compatibility and behavior errors.
- **Geo:** two tests fail because decoding a ShapeIndex reports unsupported polygon encoding version 4. The patch handles other cases but misses this encoding version.
- **Koota composite / Koota pair:** the composite patch misses 16 issue cases involving constituent change detection and tag traits. The pair patch misses four cases, including callbacks for non-first/non-last pairs, where it reads an undefined value. Both are incomplete generated implementations.
- **Vulture:** the selected patch adds cache defaults (`cache`, `cache_clear`, and `cache_dir`) to merged configuration, changing existing expected output. One concrete regression is visible in the test report.

These problems are fixable in a new model-generated repair. They do not, by themselves, show an Agentless controller bug.

### Failures where the issue tests did not produce a full report

- **Kysely:** the verifier's “base” phase runs existing regression tests on the submitted source. The earlier report mistook this phase for a build of the clean checkout. Running the pinned verifier in two fresh containers confirmed 22/22 regression tests on the clean checkout and reproduced the build failure with the exact saved patch. Its new `simplify-frame-plugin.ts` imports `../../operation-node/root-operation-node.js`, which TypeScript could not resolve. Both candidate test phases stopped before executing tests, so DeepSWE scored 0/254 issue tests and 0/22 regressions under its missing-result rule.
- **Dasel:** its issue IDs are missing because the tagged HTML package did not build. The saved model patch only adds a blank import for `parsing/html`; it does not add the parser implementation, so the selected response did not solve the task. The P2P result remains 1012/1012.
- **Obsidian automatic ToC:** its issue IDs are missing because the issue suite failed during setup: `RuleBuilderClass.getRule` was not available. The selected patch broke the API expected by the test setup, so this is a patch failure rather than evidence of a sound patch that the reporter missed. The P2P result remains 1131/1131.
- **ts-pattern:** the issue tests could not run because the selected patch caused a TypeScript type-check error at `tests/match-each.test.ts:799` (`Type 'false' does not satisfy the constraint 'true'`). This is a patch failure, not a report-mapping problem.
- **DynamoDB:** the model returned four repair responses but none became an accepted patch candidate. That is a response/edit-format failure in this run, not a test-scoring result.
- **SuperJSON:** the first two GPT-6.2 attempts stopped before receiving any model response. A later run completed normally and resolved the task, so those first two attempts remain provider failures rather than model failures; no further retry is indicated.

## Evidence

The Kysely control and saved-patch replay are under `artifacts/kysely-saved-patch-verifier-2026-11-19/`. Both used the pinned corpus revision and image. The replay matched the original patch SHA-256 `e1eebdfb6965f3b87c61226326ca1ec804a749270fa2ab75e8aa1ed1132e80f7`. There were no model calls.

Full run artifacts are retained in ignored `artifacts/` directories. Compact per-run records are in the sibling GPT-6.2 pilot folders. The first two SuperJSON attempts are under `artifacts/agentless-superjson-sol62-2026-11-18/` and `artifacts/agentless-superjson-sol62-retry-2026-11-18/`. The completed run is under `artifacts/agentless-superjson-sol62-completion-2026-11-19/`: GPT-6.2 Sol xhigh, four repair samples, pinned image `sha256:ada56382a90fbe2dd01bde0f685a1bbd0ceac556f7b802199e60dbbca6e76387`, 80/80 issue tests, 116/116 regression tests, reward 1. The run used 37,378 tokens under once-only context accounting (83,234 processed tokens including repeated context) and took about 10 minutes.
