# Grinta on Clack with GPT-6.2 Sol

Agentless-ML resolved the DeepSWE asynchronous autocomplete task. Grinta preserved every scored regression test and missed 11 issue tests. Both used GPT-6.2 Sol at xhigh through the ChatGPT subscription, a two-hour task cap, and a two-million-token budget with once-only context accounting.

| System | Issue tests | Regression tests | Budget tokens | Total processed tokens |
|---|---:|---:|---:|---:|
| Agentless-ML | 82/82 | 643/643 | 61,118 | 106,927 |
| Grinta | 71/82 | 643/643 | 183,886 | 2,024,834 |

Grinta passed the public baseline before inference and completed 29 responses over about 678 seconds. The verifier reported failures in aborting an earlier fetch, cleaning up on cancel, close or submit, retry state and cancellation, and retry backoff. DeepSWE returned reward 0 for the exported patch.

Grinta used a locally derived image with the pinned Clack image as its parent. Its source archive preserved the tracked `LICENSE` symlink after checking that it pointed to a regular file inside the checkout. Both results used the same pinned verifier image and corpus revision `0b9fabbb63b9104d678fe965e1632f2dd9eaa2ea`. Grinta's patch SHA-256 was `cc600a138f43f5f6a68bcbcb2f158b0718b878687a547ca5afc35a64515d8650`. Local evidence is under `artifacts/grinta-clack-sol62-2026-11-21/`.
