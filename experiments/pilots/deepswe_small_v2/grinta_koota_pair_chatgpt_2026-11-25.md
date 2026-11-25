# Grinta on Koota pair relation tracking

Grinta used GPT-6.2 Sol at xhigh through the ChatGPT subscription. This engineering run enabled the native verification guidance from Grinta revision `10efc2b709d3599543e6350e2420a73347ec842c` and the opt-in allowance pause. The active-time cap was two hours, and the once-only context budget was two million tokens.

The public baseline passed all 172 tests before inference. The relay recorded 29 completed model responses before the interruption. Its last usage record showed 287,718 budget tokens, 2,795,227 processed tokens, and about 13 minutes 41 seconds of active time used. No allowance pause was recorded.

Windows logged an unexpected shutdown and restarted. Docker later reported that the original container had exited with code 255 and was not marked as OOM-killed. The checkout and output directory lived in the container's RAM-backed `/tmp`. Neither path was recoverable from the stopped container, and the host had no exported patch. The verifier did not run, so this attempt has no score. No rerun was made.

Local evidence is under `artifacts/grinta-koota-pair-chatgpt-2026-11-25/`. The [earlier Agentless-ML run](vulture_koota_pair_sol62_2026-11-18/results.json) scored 34 of 38 issue tests and 172 of 172 regressions. There is no Grinta verifier result to compare with it.
