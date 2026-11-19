# Grinta on KaTeX with GPT-6.2 Sol

This single task was chosen because Agentless-ML previously left it unresolved. Both runs used GPT-6.2 Sol at xhigh through the ChatGPT subscription, a two-hour task cap, and a two-million-token budget with once-only context accounting.

| System | Issue tests | Regression tests | Budget tokens | Total processed tokens |
|---|---:|---:|---:|---:|
| Agentless-ML | 0/94 | 0/599 | 106,545 | 171,937 |
| Grinta | 94/94 | 599/599 | 173,953 | 2,154,815 |

Grinta completed in 816 seconds with 28 model responses. The pinned DeepSWE verifier returned reward 1. Corpus revision `0b9fabbb63b9104d678fe965e1632f2dd9eaa2ea`. Exported patch SHA-256 `6ad42a92d1f76a28f1e1d04b293e1d927b70687d04230d6052ee9cdbec71f951`.

The run used a local copy of the Grinta launcher and a derived KaTeX image. Setup checks caught a session lock directed at the read-only home, a missing GPT-6.2 catalog entry, and a provider rejection of conditional tool schema keywords. The final setup stored session state in the existing scratch space, registered GPT-6.2 Sol, and adapted the provider-facing tool schema. Grinta's local argument validation remained in place. The setup failures produced zero completed model responses. This is an engineering pilot on one selected task.

Local outputs are under `artifacts/grinta-katex-sol62-2026-11-19/`. The completed attempt is in `schema-attempt/` and the verifier report is in `score/`. The earlier Agentless-ML result is in [the paired model comparison](gpt61_vs_gpt62_twenty_tasks_2026-11-18/README.md).
