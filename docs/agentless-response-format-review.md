# Symbol-localization response format

The first live Aiomonitor retry returned locations without Markdown fences.
Our symbol-localization parser extracted no blocks, so the workflow stopped
before repair generation. This review checks whether that was our own format
restriction or inherited Agentless behavior.

## What the pinned source does

The reference is Agentless v1.5.0, commit
`b150f28465a77a81a7f4776384957a4271f5bd69`.
Before the clarification below, the Python compressed-file symbol prompt in our adapter was byte-identical to
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

## Correction, 30 October 2026

We made the final Python symbol-localization instruction explicit:

> Return just the locations inside an unlabelled fenced code block, as shown above.

Previously it said only to return the locations. This is a one-sentence prompt
clarification relative to the pinned reference, and the Python prompt golden has
been updated to record it. The example, location vocabulary, parser, workflow
and sampling policy are unchanged. Other languages already explicitly request
an unlabelled fenced block through their shared prompt suffix.

The failure exposed an ambiguity inherited from the pinned prompt: its example
uses fences but its closing instruction does not require them. Our original copy
was correct. Making that requirement explicit aligns the instruction with the
existing parser; it does not guarantee that every future model response will
follow the format. An unfenced response still yields no symbol blocks.

The initial review on 29 October preserved both components. This later change
was explicitly approved by Youssef. Earlier failed attempts and their prompts
remain historical evidence; they have not been rewritten. No new model attempt
was run to validate the clarification. This comparison does not establish parity
for the whole upstream workflow's handling of failed localization.

Evidence is saved in
`experiments/pilots/deepswe_small_v2/format_and_runtime_review_2026-10-29.json`.
The original review's location-parity and prompt-golden checks passed: 18 tests.
The same 18 checks passed after the clarification with the updated Python golden;
the other languages' goldens did not change. These checks and the source
comparison used no model calls.
