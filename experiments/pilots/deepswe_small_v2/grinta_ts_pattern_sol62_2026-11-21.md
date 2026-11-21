# Grinta on ts-pattern with GPT-6.2 Sol

Both systems left the DeepSWE `matchEach` task unresolved using GPT-6.2 Sol at xhigh through the ChatGPT subscription. Both used a two-hour task cap and a two-million-token budget with once-only context accounting.

| System | Issue tests | Regression tests | Budget tokens | Total processed tokens |
|---|---:|---:|---:|---:|
| Agentless-ML | 0/85 | 6/6 | 38,504 | 75,178 |
| Grinta | 0/85 | 6/6 | 135,471 | 1,505,768 |

Both submitted patches failed the same TypeScript assertion at `tests/match-each.test.ts:799`. The compiled matcher was expected to have type `(input: 'b' | 'c') => number[]`. The issue suite stopped at type checking, and DeepSWE counted all missing issue results as failed.

Grinta's public baseline passed before inference. The relay recorded 27 completed responses over about 676 seconds, and Grinta finished and exported its patch. The Grinta runtime was derived from the pinned task image. The external verifier used corpus revision `0b9fabbb63b9104d678fe965e1632f2dd9eaa2ea` and returned reward 0. Grinta's patch SHA-256 was `31cdcfa6d2087f836ae9763a2a25b733afe376555442b0f8e694077ec7592fdb`. Local evidence is under `artifacts/grinta-ts-pattern-sol62-2026-11-21/`.
