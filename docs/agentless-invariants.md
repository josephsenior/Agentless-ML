# What defines the Agentless-ML condition?

The purpose of Agentless-ML is not simply to reproduce the shape of an older
codebase. It is to preserve a meaningful fixed-workflow experimental condition
while removing assumptions that prevent evaluation on newer benchmarks.

The distinction below is part of the research protocol. Changes to the first
list alter the experimental condition and require an explicit design decision.

## Properties we preserve

1. **A fixed controller.** The high-level order is localization, repair,
   validation, and selection. The model does not choose arbitrary next actions.
2. **Hierarchical localization.** The system narrows the repository from files,
   to program elements, to specific edit locations.
3. **Focused repair context.** Repair receives source selected by the controller,
   not an unrestricted interactive repository session.
4. **Breadth through sampling.** Multiple localization or repair candidates may
   be generated, but each follows the same controller-defined stages.
5. **Controller-owned validation.** Tests can filter or rank candidates. Their
   output cannot start a new open-ended model trajectory.
6. **Deterministic selection.** Given the same recorded candidates and test
   outcomes, filtering, normalized-patch voting, and tie-breaking produce the
   same final patch.
7. **No persistent adaptive tool state.** There is no general
   act–observe–decide loop spanning arbitrary repository operations.
8. **A sealed final verifier.** Hidden tests and reference solutions are not
   available during localization, generation, or candidate selection.

## Details we can modernize

The following are interfaces rather than defining properties:

- benchmark records and dataset loaders;
- preparation of pinned repositories and task containers;
- language parsers and their grammar-specific nodes;
- public build and test commands;
- model-provider clients;
- logging, accounting, and reproducibility metadata.

Modernizing one of these details must not change the information shown to one
experimental condition but not the other.

## What this project is not

Agentless-ML is not a general shell agent or an autonomous coding environment.
It also does not retroactively make the published Agentless release multilingual.
The published implementation remains a separate regression reference, and its
results must be labelled separately from Agentless-ML results.
