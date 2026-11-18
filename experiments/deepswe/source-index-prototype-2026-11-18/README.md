# Offline source-discovery check, 18 November 2026

These are source-visibility measurements, not model or benchmark results.
No model requests, generated repairs, Docker runs or scoring calls were made.
The production Agentless-ML workflow is unchanged.

See the [design and findings](../../../docs/source-index-prototype.md) for the
method, measurements and limits. `cases.json` records the pinned repositories,
saved file selections, public issue paths and optional declaration checks.
The three task JSON files retain counts, hashes, expanded paths and import
witnesses for the checked declarations. The checked names never seed expansion.

The full raw outputs are local under
`artifacts/offline-source-index-2026-11-18/<task>/`:

- `source-index.txt`: every indexed file and recognized declaration.
- `file-localization-with-index.txt`: reconstructed file prompt with the index.
- `expanded-index.txt`: declarations in the outgoing import closure.
- `graph.json`: import candidates and exclusion/analysis diagnostics.
- `expansion.json`: import witnesses and unresolved links in the closure.
- `summary.json`: the runner's measurements before adding this evidence record's
  convenience fields for witness chains and local artifact locations.

The raw index, prompt, expanded-index and expanded-source hashes matched on a
second pass for all three tasks. Token estimates use `o200k_base`. Source spans
refer to public base revisions, not the current working-tree files. Previous
task outcomes remain under their original configurations.
