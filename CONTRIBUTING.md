# Contributing

Agentless-ML has a recorded multilingual workflow; live-model execution and the
research protocol are still being completed. Issues and focused pull requests
are welcome, especially when they improve reproducibility or expose a
behavioral difference from a pinned reference.

## Before opening a change

Please read [the experimental invariants](docs/agentless-invariants.md). Changes
to the controller, model-visible information, hidden-test isolation, or final
selection policy are research-design changes and should be discussed before
implementation.

## Local checks

```bash
uv sync --extra dev
uv run pytest
```

Tests should not depend on private checkout paths, network access, model APIs, or
hidden benchmark data. If a change affects published Agentless parity, regenerate
the relevant fixture with the matching script in `tools/` and explain why the
golden output changed.

## Documentation and generated files

Keep current behavior in the [main guides](docs/README.md) and date-specific
investigations in `docs/history/`. Update relative links when moving a note.
Describe a new command in [the tools guide](tools/README.md), including whether
it is a reusable entry point or a diagnostic tied to one task.

Keep compact run evidence under `experiments/` and large local outputs out of
Git. Follow [the retention notes](experiments/README.md#raw-outputs-and-cleanup)
before deleting artifacts. A cleanup must preserve cited results, fixture
provenance and unrelated local edits; it must not make old failures disappear
or silently change an experimental condition.

## Pull requests

A useful pull request states:

- which experimental condition or interface it affects;
- whether model-visible information changes;
- which upstream and benchmark revisions were used;
- how the change was tested;
- any known difference from the published Agentless behavior.
