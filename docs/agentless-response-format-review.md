# Symbol-localization response format

The first live Aiomonitor retry returned locations without Markdown fences.
Our symbol-localization parser extracted no blocks, so the workflow stopped
before repair generation. This review checks whether that was our own format
restriction or inherited Agentless behavior.

## What the pinned source does

The reference is Agentless v1.5.0, commit
`b150f28465a77a81a7f4776384957a4271f5bd69`.
The Python compressed-file symbol prompt in our adapter is byte-identical to
`LLMFL.obtain_relevant_functions_and_vars_from_compressed_files_prompt_more`
in the pinned [FL.py](https://github.com/OpenAutoCoder/Agentless/blob/b150f28465a77a81a7f4776384957a4271f5bd69/agentless/fl/FL.py).
Its example is fenced, but its final instruction only says to return locations.

The pinned [block extractor](https://github.com/OpenAutoCoder/Agentless/blob/b150f28465a77a81a7f4776384957a4271f5bd69/agentless/util/postprocess_data.py)
and ours both extract unlabelled fenced blocks. Both also have a permissive
fallback when the answer contains a fence marker but no matching complete block.
Neither accepts an answer containing no fence marker at all at this stage.
File localization has a separate plain-text fallback; that does not establish
the same behavior for symbol localization.

We compared both extractors on the retained live response, that same text inside
fences, an incomplete fence and a labelled fence. Their outputs matched in all
four cases. The original response yielded zero blocks; wrapping it yielded one.
This only verifies extraction: some listed symbols were not present in the base
revision, and wrapping the answer does not establish that the task is solved.

## Decision

Keep the pinned Python prompt and parsing behavior for now. There is no local
replication error to correct in these two components. The failure exposes a
prompt/parser mismatch inherited from this pinned configuration, rather than a
reason to silently accept additional response formats.

If we decide to make the instruction explicitly request fences, record it as a
prompt variation and update its prompt golden. Accepting unfenced symbols would
instead change parsing behavior. Neither change, and no further live retry, was
made during this review. This comparison does not establish parity for the whole
upstream workflow's handling of failed localization.

Evidence is saved in
`experiments/pilots/deepswe_small_v2/format_and_runtime_review_2026-10-29.json`.
The existing location-parity and prompt-golden checks passed: 18 tests. These
checks and the source comparison used no model calls.
