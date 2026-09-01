# ADR 0001: Build the generalized baseline separately

- **Status:** Accepted
- **Date:** 2026-08-31

## Context

The published Agentless v1.5.0 implementation is closely tied to Python, the
original SWE-bench data format, a fixed set of repository names, and the model
interfaces available at the time. Our planned evaluation needs a fixed workflow
that can run across languages and benchmark harnesses without pretending that
those original assumptions are part of the Agentless idea itself.

Editing the published repository in place would blur two questions: whether we
faithfully understand its behavior, and whether the generalized design works.

## Decision

Agentless-ML is maintained as a separate implementation. The published checkout
is pinned and left unchanged. We compare the two at observable boundaries such
as Python structure extraction, prompt construction, location resolution, patch
normalization, and reranking.

Every intentional difference is recorded under one of five headings:

- benchmark integration;
- multilingual support;
- model compatibility;
- candidate validation;
- instrumentation.

## Consequences

This costs more engineering time than patching the original repository, but it
keeps the experiment interpretable. A passing parity test supports a specific
behavioral claim; it does not imply that the implementations are identical.

Published Agentless reproduction results and Agentless-ML benchmark results are
reported as separate conditions. If a modernization changes model-visible
information or controller behavior, it must be disclosed rather than described
as routine compatibility work.
