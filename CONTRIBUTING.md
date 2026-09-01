# Contributing

Agentless-ML is currently a small research prototype. Issues and focused pull
requests are welcome, especially when they improve reproducibility or expose a
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

## Pull requests

A useful pull request states:

- which experimental condition or interface it affects;
- whether model-visible information changes;
- which upstream and benchmark revisions were used;
- how the change was tested;
- any known difference from the published Agentless behavior.
