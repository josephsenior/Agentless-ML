# Grinta on Meriyah with GPT-6.2 Sol

Grinta ran the DeepSWE explicit resource declarations task using GPT-6.2 Sol at xhigh through the ChatGPT subscription. It reused the KaTeX pilot's Grinta launcher and provider settings, with Meriyah's pinned source and task image. The public baseline passed before inference. The run used the same two-hour cap and two-million-token budget with once-only context accounting.

The pinned verifier scored the exported patch **unresolved** with reward 0. It passed 45 of 49 issue tests and all 51,469 regression tests. The four failures covered a `using` declaration in a switch case, array destructuring in `using` and `await using`, and a `for…of` loop with a `using` binding named `of`.

The relay recorded 36 completed model responses over 882 seconds, with 215,402 budget tokens and 3,213,249 processed tokens including repeated context. The subscription remained available through the attempt.

Local output is under `artifacts/grinta-meriyah-sol62-2026-11-19/`. The verifier used corpus revision `0b9fabbb63b9104d678fe965e1632f2dd9eaa2ea`. The exported patch SHA-256 was `bfb120983dd8af4642d3479953effdbaf120846bc9fac087a12cc909b6b060ba`. The submitted patch includes a new test file and an existing snapshot update.
