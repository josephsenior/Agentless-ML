# Agentless-ML KaTeX follow-up

The KaTeX follow-up ran Agentless-ML at `b1724fb` with GPT-6.1 Sol at medium
reasoning, one edit-localization sample, four repairs, and the 2M content-token
and two-hour caps. The pinned checkout was `89bede495dc2c85e1c57ba627a18526f71d57396`.

The model selected three tracked TypeScript files: `src/environments/array.ts`,
`src/parseNode.ts`, and `src/Parser.ts`. All three passed file localization and
the run proceeded through symbol and edit localization to repair generation.
This cleared the source-visibility blocker from the earlier pilot.

Two repairs contained SEARCH blocks rejected as outside authorized intervals,
one in `src/environments/array.ts` and one in `src/parseNode.ts`. The other
two responses had no SEARCH/REPLACE edits. No candidate reached public
validation, so there was no exported prediction or held-out verifier score.

Eight requests completed, using 77,143 once-only content tokens and 86,163
provider-reported tokens (71,852 input and 14,311 output). The workflow
clock used about 510 seconds. Local evidence is under
`artifacts/agentless-katex-live-2026-11-05`.
