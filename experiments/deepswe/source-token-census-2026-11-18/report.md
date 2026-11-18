# Offline DeepSWE source-context token census

Token estimates use o200k_base. No model calls; production workflow unchanged.

Index/map columns are whole reconstructed file-localization prompts, including issue and tree.
The 8k map is only an illustrative lexical whole-row cap; omitted edges may be needed.
Inspection is the sum of the ten largest standalone source skeletons (or all files if fewer).
It is a payload size scenario, not an actual selection or a complete second request.

| Task | Index prompt | + full import map | + 8k map | Largest-10 skeleton payload | Caveats |
| --- | ---: | ---: | ---: | ---: | --- |
| abs-module-cache-flags | 7,727 | 8,393 | 8,404 | 18,268 |  |
| abs-stepped-slices | 7,988 | 8,654 | 8,665 | 18,268 |  |
| actionlint-action-pinning-lint | 13,119 | 23,082 | 21,016 | 88,651 |  |
| adaptix-name-mapping-aliases | 40,921 | 63,010 | 48,796 | 16,424 |  |
| aiomonitor-task-snapshots-diff | 3,272 | 4,258 | 4,269 | 4,592 |  |
| anko-default-function-arguments | 5,132 | 17,784 | 13,106 | 25,364 |  |
| anko-typed-variable-bindings | 5,343 | 17,995 | 13,317 | 25,364 |  |
| arcane-drift-detection-baselines | 100,085 | 172,905 | 107,532 | 53,289 | 8 parse errors; skeleton payload partial |
| arktype-json-schema-refs-dependencies | 41,528 | 53,728 | 49,520 | 149,759 | 24 parse errors; skeleton payload partial |
| awilix-async-container-initialization | 3,390 | 4,134 | 4,145 | 7,778 |  |
| bandit-incremental-cache-control | 10,597 | 15,199 | 15,210 | 34,166 | 2 unreadable blobs; partial count; 2 parse errors |
| bandit-interprocedural-taint-checks | 10,539 | 15,141 | 15,152 | 34,266 | 2 unreadable blobs; partial count; 2 parse errors |
| bandit-structured-nosec-directives | 10,818 | 15,420 | 15,431 | 34,266 | 2 unreadable blobs; partial count; 2 parse errors |
| boa-hierarchical-evaluation-cancellation | 269,746 | 288,145 | 277,743 | 133,492 | 2 parse errors; Rust import map unsupported; skeleton payload partial |
| cattrs-partial-structuring-recovery | 5,905 | 8,445 | 8,456 | 8,419 |  |
| clack-async-autocomplete-options | 7,164 | 8,868 | 8,879 | 5,359 |  |
| claude-code-by-agents-recursive-delegation | 11,824 | 15,187 | 15,198 | 8,278 |  |
| cliffy-config-file-parsing | 51,576 | 57,304 | 57,315 | 89,724 | 4 parse errors; skeleton payload partial |
| csstree-shorthand-expansion-compression | 15,302 | 21,666 | 21,677 | 8,694 | 1 parse errors |
| dasel-html-document-format | 8,852 | 29,944 | 16,732 | 5,434 |  |
| dateutil-rfc5545-timezone-interop | 6,509 | 7,300 | 7,311 | 8,384 |  |
| drizzle-orm-window-function-builders | 111,858 | 144,798 | 119,831 | 793,304 | 11 parse errors; skeleton payload partial |
| dynamodb-toolbox-conditional-attribute-requirements | 37,147 | 57,776 | 45,056 | 23,227 | 1 parse errors; skeleton payload partial |
| dynamodb-toolbox-lazy-recursive-schemas | 37,176 | 57,805 | 45,085 | 23,227 | 1 parse errors; skeleton payload partial |
| effect-sse-httpapi-streaming | 166,897 | 209,482 | 174,897 | 2,262,932 | 311 parse errors; skeleton payload partial |
| eicrud-keyset-pagination-cursor | 15,184 | 18,046 | 18,057 | 14,986 | 5 parse errors; skeleton payload partial |
| etree-xml-diff-patch | 3,993 | 4,059 | 4,070 | 10,693 |  |
| expr-try-catch-errors | 20,535 | 26,823 | 26,834 | 61,320 |  |
| fastapi-deprecation-response-headers | 33,560 | 48,404 | 41,536 | 80,698 |  |
| fastapi-implicit-head-options | 33,182 | 48,026 | 41,158 | 80,698 |  |
| fd-deterministic-multi-key-sorting | 7,153 | 7,577 | 7,588 | 19,357 | Rust import map unsupported |
| geo-shapeindex-serialization | 19,716 | 47,178 | 27,660 | 42,623 |  |
| go-critic-doc-link-checker | 10,850 | 69,780 | 18,506 | 40,703 |  |
| go-genai-streamed-function-args | 19,407 | 26,541 | 26,552 | 86,032 |  |
| go-git-worktree-merge-conflicts | 44,100 | 95,905 | 51,744 | 41,699 |  |
| goreleaser-retry-publish-auditing | 25,962 | 42,076 | 33,923 | 34,811 |  |
| gql-incremental-graphql-delivery | 8,414 | 11,335 | 11,346 | 12,055 |  |
| happy-dom-abort-pending-body-reads | 121,066 | 173,724 | 129,029 | 70,171 |  |
| happy-dom-deterministic-intersectionobserver | 121,239 | 173,897 | 129,202 | 70,171 |  |
| helm-array-merge-strategies | 32,273 | 92,121 | 40,184 | 28,316 |  |
| helm-unified-manifest-stream | 31,942 | 91,790 | 39,853 | 28,316 |  |
| httpx-deterministic-cookie-store | 7,664 | 8,758 | 8,769 | 15,044 |  |
| httpx-multipart-response-parsing | 7,403 | 8,497 | 8,508 | 15,044 |  |
| httpx-streaming-json-iteration | 7,506 | 8,600 | 8,611 | 15,044 |  |
| igel-persist-feature-schema | 2,964 | 4,012 | 4,023 | 7,887 |  |
| ink-grid-box-layout | 9,758 | 12,533 | 12,544 | 13,675 |  |
| ipython-session-bundle-replay | 37,330 | 45,859 | 45,301 | 41,709 |  |
| katex-multicolumn-array-spans | 20,014 | 24,920 | 24,931 | 115,278 | 2 parse errors |
| kcp-go-multiplexed-kcp-streams | 4,915 | 6,962 | 6,973 | 14,047 |  |
| kea-atomic-signal-selectors | 4,173 | 5,300 | 5,311 | 7,897 | 1 parse errors; skeleton payload partial |
| kgateway-consistent-hash-policy | 82,045 | 191,671 | 89,803 | 80,714 | 21 parse errors; Rust import map unsupported; skeleton payload partial |
| kombu-single-active-consumer-priority | 26,887 | 32,155 | 32,166 | 15,153 |  |
| kombu-virtual-queue-dead-lettering | 26,971 | 32,239 | 32,250 | 15,153 |  |
| koota-composite-trait-aspects | 16,689 | 31,074 | 24,683 | 8,711 |  |
| koota-deferred-mutation-buffer | 12,427 | 22,943 | 20,339 | 8,477 |  |
| koota-entity-snapshot-rollback | 16,901 | 31,286 | 24,895 | 8,711 |  |
| koota-pair-relation-tracking | 16,571 | 30,956 | 24,565 | 8,711 |  |
| koota-query-predicates | 16,554 | 30,939 | 24,548 | 8,711 |  |
| kysely-window-grouping-helpers | 57,592 | 82,954 | 65,344 | 89,137 | 2 parse errors; skeleton payload partial |
| langchain-request-coalescing | 163,221 | 212,171 | 171,198 | 41,392 |  |
| mashumaro-flattened-dataclass-fields | 10,770 | 14,738 | 14,749 | 12,161 |  |
| meriyah-explicit-resource-declarations | 35,664 | 37,077 | 37,088 | 61,000 | 3 parse errors; skeleton payload partial |
| mnamer-daemon-watch-lifecycle | 3,163 | 3,810 | 3,821 | 6,699 |  |
| mobly-grouped-test-barriers | 11,473 | 13,845 | 13,856 | 9,949 |  |
| narwhals-rolling-window-suite | 59,962 | 75,550 | 67,909 | 36,484 |  |
| numba-stencil-boundary-modes | 144,021 | 169,481 | 152,006 | 97,139 | 1 parse errors |
| obsidian-linter-auto-table-of-contents | 23,092 | 28,715 | 28,726 | 89,242 |  |
| obsidian-linter-link-format-conversion | 23,276 | 28,899 | 28,910 | 89,242 |  |
| obsidian-linter-scoped-ignore-markers | 23,184 | 28,807 | 28,818 | 89,242 |  |
| ofetch-per-origin-circuit-breaker | 2,187 | 2,538 | 2,549 | 2,416 | 1 parse errors; skeleton payload partial |
| onedump-dump-encryption-pipeline | 5,174 | 6,655 | 6,666 | 6,078 |  |
| opa-rego-rule-profiling | 128,997 | 293,594 | 136,779 | 104,464 | 2 parse errors; skeleton payload partial |
| opa-template-string-reconstruction | 128,512 | 293,109 | 136,294 | 104,464 | 2 parse errors; skeleton payload partial |
| optique-conditional-option-dependencies | 16,568 | 18,816 | 18,827 | 80,004 |  |
| oxvg-structural-selector-preservation | 52,632 | 57,126 | 57,137 | 79,687 | 1 parse errors; Rust import map unsupported; skeleton payload partial |
| participle-grammar-conflict-analysis | 4,929 | 6,358 | 6,369 | 8,168 |  |
| pebble-durability-wait-apis | 119,086 | 260,431 | 127,064 | 99,298 |  |
| pest-character-class-coalescing | 20,778 | 21,954 | 21,965 | 967,575 | Rust import map unsupported |
| prometheus-transactional-reload-status | 140,349 | 224,784 | 148,316 | 137,070 | 1 parse errors; skeleton payload partial |
| prometheus-typed-label-sorting | 140,268 | 224,703 | 148,235 | 137,070 | 1 parse errors; skeleton payload partial |
| psd-tools-blend-range-api | 19,321 | 23,473 | 23,484 | 42,239 |  |
| pwntools-tube-multiplexing | 439,004 | 450,335 | 446,952 | 333,636 |  |
| python-statemachine-state-data-scoping | 10,307 | 13,062 | 13,073 | 9,872 |  |
| query-persist-restored-query-state | 57,657 | 82,545 | 65,636 | 31,012 |  |
| quill-shared-toolbar-focus | 13,779 | 18,285 | 18,296 | 12,110 | 2 parse errors; skeleton payload partial |
| returns-validated-error-accumulation | 16,170 | 22,908 | 22,919 | 15,983 |  |
| scc-bounded-memory-spilling | 5,635 | 7,802 | 7,813 | 92,983 | 1 parse errors |
| scriggo-method-declarations | 25,290 | 39,854 | 33,102 | 37,929 |  |
| skrub-duration-encoding | 23,871 | 29,117 | 29,128 | 23,190 |  |
| sql-formatter-bigquery-pipe-formatting | 11,483 | 15,166 | 15,177 | 42,884 |  |
| sqlfmt-create-table-ddl-formatting | 4,936 | 6,848 | 6,859 | 10,993 |  |
| sqlite-utils-safe-import-checkpoints | 4,405 | 4,681 | 4,692 | 16,560 |  |
| superjson-error-stack-serialization | 2,829 | 3,155 | 3,166 | 3,899 |  |
| task-task-graph-export | 12,841 | 26,569 | 20,708 | 11,542 |  |
| tengo-callable-instance-isolation | 13,357 | 18,951 | 18,962 | 24,520 |  |
| tengo-destructuring-bindings | 13,341 | 18,935 | 18,946 | 24,520 |  |
| termenv-preserve-ansi-resets | 3,946 | 6,049 | 6,060 | 8,035 |  |
| testem-bail-on-test-failure | 17,924 | 22,327 | 22,338 | 19,076 |  |
| testem-per-launcher-reports | 17,908 | 22,329 | 22,340 | 19,363 |  |
| textual-kitty-key-phases | 78,354 | 106,992 | 86,338 | 43,832 |  |
| textual-richlog-follow-state | 78,435 | 107,073 | 86,419 | 44,023 |  |
| tomlkit-toml-table-converters | 6,105 | 6,633 | 6,644 | 9,194 |  |
| true-myth-iterable-collection-combinators | 6,359 | 6,654 | 6,665 | 62,877 |  |
| ts-pattern-match-each | 4,280 | 5,069 | 5,080 | 26,820 |  |
| updo-policy-alerting | 5,390 | 6,774 | 6,785 | 7,077 |  |
| valibot-recursive-schema-composition | 145,678 | 221,547 | 153,663 | 66,460 | 4 parse errors; skeleton payload partial |
| vitest-duration-sharding | 92,920 | 117,815 | 100,905 | 59,958 | 5 parse errors; skeleton payload partial |
| vulture-persistent-analysis-cache | 2,490 | 3,119 | 3,130 | 1,706 |  |
| wasmi-trap-coredumps | 104,966 | 110,366 | 110,377 | 98,660 | 1 parse errors; Rust import map unsupported; skeleton payload partial |
| wazero-multi-module-snapshots | 93,553 | 188,179 | 101,438 | 152,631 | Rust import map unsupported |
| yaegi-go-embed-directives | 56,454 | 1,387,424 | 63,093 | 33,373 |  |
| yjs-map-conflict-detection | 8,685 | 9,812 | 9,823 | 22,514 |  |
| ytt-jsonpath-query-api | 27,286 | 59,656 | 35,059 | 28,660 |  |
