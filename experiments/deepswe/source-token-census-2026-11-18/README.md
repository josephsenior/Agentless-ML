# Source-context token census, 18 November 2026

Offline measurements of the pinned 113-task corpus. No model calls, generated
repairs, benchmark test runs or production workflow changes.

- [Per-task counts](report.md): reconstructed file-localization prompts with
  declaration indexes and import-map scenarios; largest-ten skeleton payloads.
- [Compact measurements](measurements.json): pins, hashes, counts and caveats.
- [Aggregate statistics](statistics.json): distributions and threshold counts.
- [Interpretation and possible inspection phase](../../../docs/source-context-census.md).

Full local records are under `artifacts/source-token-census-2026-11-18/`.
The runner is `tools/survey_source_index_tokens.py`. Token estimates use
`o200k_base`, not provider usage reports. They exclude model output and do not
predict total experiment consumption. The 8k map is an illustrative lexical cap,
not an adopted relevance policy; it can omit needed dependencies. Inspection
payloads use actual existing skeleton rendering, including retained literals.

Unreadable blobs and parser limitations are preserved in the evidence. Affected
counts are partial. The graph is based on static file imports, with Rust import
analysis unsupported. None of these source measurements changes task scores or
eligibility. Use the guide before drawing conclusions from the table.
