# ADR 0002: Generalize parsing through language adapters

- **Status:** Provisional; Python implemented, additional languages pending
- **Date:** 2026-09-07

## Context

Agentless localizes files and program elements before constructing repair context.
Python-specific syntax cannot describe all of the constructs in the planned Go,
JavaScript/TypeScript and Rust support. The fixed workflow should remain comparable
across those languages.

## Decision

Put each language's parsing code in an adapter and keep the stage order and
candidate-selection rules shared. Change the common representation when a new
language needs something it cannot express yet.

The controller still uses Python directly. Next we will implement Go, then
JavaScript/TypeScript and Rust, testing each with recorded responses. We will
adjust the shared representation as we go. Python alone is not enough to tell us
whether it works for the other languages.

## Alternatives

- Separate controllers per language would allow local flexibility but duplicate
  workflow policy and make accidental experimental differences easier to introduce.
- Language conditionals throughout the controller would start simply but distribute
  parsing assumptions across code that should describe the shared method.
- Freezing a universal representation from Python alone would commit to assumptions
  that the other languages have not tested.

## Consequences

For each language, we need to explain how its functions, types and other constructs
appear in the shared representation. We also need to inspect the source context
shown to the model: running the same stages does not mean we have selected equally
useful context. The existing Python fixtures help us check for unintended changes
while adding the other languages.

Luna transport and official benchmark scoring are later integration work. Neither
determines how a language adapter should represent source code.
