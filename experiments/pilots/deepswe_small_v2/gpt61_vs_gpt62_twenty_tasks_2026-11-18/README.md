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
| Dasel HTML document format | 0/146, 406/1012 | 0/146, 1012/1012 | P2P improved; 6.2 issue IDs were unreported, so no solve claim |
| DynamoDB Toolbox conditional attribute requirements | No patch candidate | No patch candidate | Neither run produced a scoreable patch |
| Kysely window grouping helpers | No patch candidate | Score says 0/254 and 0/22, but both base and patched builds failed | Not a valid performance comparison |
| Mobly grouped test barriers | 79/79, 808/808, resolved | 36/79, 808/808, unresolved | 6.1 was better |
| Obsidian link format conversion | 0/60, 1131/1131 | 0/60, 582/1131 | 6.1 preserved more tests; 6.2 did not solve the issue |
| Obsidian automatic table of contents | 0/41, 582/1131 | 0/41, 1131/1131 | 6.2 preserved more tests; issue IDs were unreported in both runs |
| etree XML diff patch | 52/52, 15/15, resolved | 52/52, 15/15, resolved | Same result |
| Obsidian scoped ignore markers | 33/33, 1133/1133, resolved | 33/33, 1131/1133, unresolved | 6.1 was better; 6.2 regressed two existing tests |
| Koota composite trait aspects | 5/51, 172/172 | 35/51, 172/172 | 6.2 made substantial issue-test progress; neither resolved it |
| SuperJSON error stack serialization | 80/80, 116/116, resolved | No model response on two attempts | No valid model comparison |
| Incremental GraphQL delivery | 14/17, 810/811 | 14/17, 810/811 | Same result |
| Geo ShapeIndex serialization | 0/24, 532/599 | 22/24, 599/599 | 6.2 was clearly better, but still missed two issue checks |
| HTTPX deterministic cookie store | Timed out after 6/8 model responses; no score | 115/115, 1281/1281, resolved | 6.2 completed a solve; 6.1 has no scored result to compare |
| Narwhals rolling window suite | 91/103, 10093/10093 | 103/103, 10093/10093, resolved | 6.2 resolved it |
| Koota pair relation tracking | No patch candidate in the earlier runs | 34/38, 172/172 | 6.2 produced a useful partial patch |
| ts-pattern matchEach | 0/85, 6/6 | 0/85, 6/6 | Same score; 6.2 issue IDs were unreported |
| Vulture persistent analysis cache | 24/24, 294/295 | 24/24, 290/295 | 6.1 preserved four more existing tests |
| KaTeX multicolumn array spans | 84/94, 599/599 | 0/94, 0/599 | 6.1 was better; the 6.2 patch broke test-suite loading |

## Overall comparison

GPT-6.2 had better measured results on eight tasks: Awilix, Clack, Dasel's existing-test preservation, Geo, Koota composite, Koota pair, Narwhals, and Obsidian automatic ToC's existing-test preservation. HTTPX also resolved under 6.2 after the 6.1 run timed out, though that is not a score-for-score pair.

GPT-6.1 had better results on five tasks: Mobly, Obsidian link conversion, Obsidian scoped ignore markers, Vulture, and KaTeX. Four tasks had the same score or same no-patch outcome: etree, GraphQL, ts-pattern, and DynamoDB. Kysely and SuperJSON do not support a clean model comparison because their 6.2 attempts could not produce a valid scored run.

This does **not** establish that GPT-6.2 is generally superior. The 6.2 runs solved Awilix, Clack, and Narwhals where the earlier runs missed one or more issue tests, and made strong partial progress on Geo and Koota. But the 6.1 run solved Mobly and Obsidian scoped ignore where the 6.2 selected patches failed, and 6.1 produced a much stronger KaTeX result. The outcomes depend on the generated patch and selection for that particular run.

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

### Results that need evaluator or setup investigation

- **Kysely:** the verifier says both the base build and patched build fail to resolve `../../operation-node/root-operation-node.js`. Because the unmodified base fails too, the 0/254 and 0/22 score is not a valid judgment of the model patch.
- **Dasel, Obsidian automatic ToC, and ts-pattern:** their GPT-6.2 F2P tests are all marked “missing from report.” The issue-test score is therefore not reliable evidence that the patch failed each issue case. The relevant test invocation/report mapping needs inspection.
- **DynamoDB:** the model returned four repair responses but none became an accepted patch candidate. That is a response/edit-format failure in this run, not a test-scoring result.
- **SuperJSON:** both GPT-6.2 attempts stopped at regression selection with `Subscription response failed`; zero model responses completed. The recorded error does not tell whether the cause was sign-in, allowance, or a temporary stream failure. This is a provider blocker, not a model failure.

## Evidence

Full run artifacts are retained in ignored `artifacts/` directories. Compact per-run records are in the sibling GPT-6.2 pilot folders. The attempted SuperJSON runs are under `artifacts/agentless-superjson-sol62-2026-11-18/` and `artifacts/agentless-superjson-sol62-retry-2026-11-18/`.
