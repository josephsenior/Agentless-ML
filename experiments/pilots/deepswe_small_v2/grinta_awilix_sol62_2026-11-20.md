# Grinta on Awilix with GPT-6.2 Sol

Both systems resolved the DeepSWE asynchronous container initialization task using GPT-6.2 Sol at xhigh through the ChatGPT subscription. Both used a two-hour task cap and a two-million-token budget with once-only context accounting.

| System | Issue tests | Regression tests | Budget tokens | Total processed tokens |
|---|---:|---:|---:|---:|
| Agentless-ML | 24/24 | 162/162 | 52,483 | 100,483 |
| Grinta | 24/24 | 162/162 | 194,114 | 2,874,958 |

Grinta's public baseline passed before inference. The relay recorded 36 completed responses over 753 seconds. DeepSWE returned reward 1 for the exported patch. The verifier used corpus revision `0b9fabbb63b9104d678fe965e1632f2dd9eaa2ea`. Grinta's patch SHA-256 was `7fa7d334ab30fa53fbc5019c44077d1ec6ec60e3adb9b8543ff15c8a5524c51d`. Local evidence is under `artifacts/grinta-awilix-sol62-2026-11-20/`.

Pebble was attempted first. Its public baseline reported a new lint failure in `TestLint/TestForbiddenImports` compared with the saved report. The launcher stopped before model inference. Pebble has no score. Its baseline evidence is under `artifacts/grinta-pebble-sol62-2026-11-20/attempt/`.
