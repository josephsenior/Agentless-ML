# What we kept from Agentless, and what we changed

This note records what the current implementation reproduces, what it changes,
and what we have actually checked. The reference is Agentless v1.5.0, commit
`b150f28465a77a81a7f4776384957a4271f5bd69` (see [provenance](../PROVENANCE.md)).
So far, we have compared specific Python outputs and run the controller with saved
responses. We have not reproduced the published benchmark results.

## Mapping the implementation

| Area | Published reference | Current Agentless-ML behavior | Evidence and limit |
|---|---|---|---|
| Workflow | Localization, repair sampling, patch validation and reranking | Shared controller consumes supplied localization and repair responses across five languages | [Python](../tests/test_fixed_workflow.py), [Go](../tests/test_go_workflow.py), [JavaScript/TypeScript](../tests/test_javascript_workflow.py) and [Rust tests](../tests/test_rust_workflow.py) check recorded execution and artifacts. No live sampling or complete upstream orchestration parity. |
| Python structure | Python AST extraction and LibCST skeletons | A legacy projection captures upstream quirks; `PythonAdapter` also exposes normalized structure | [Python tests](../tests/test_python_parity.py) and [scope](python-parity.md). Normalized nesting and async handling intentionally differ. |
| Localization and context | Hierarchical localization and bounded source context | File and symbol responses, optionally followed by recorded edit-line samples with their own repair groups, resolve to repair context | [Repository parity](../tests/test_repository_context_parity.py), [location parity](../tests/test_location_context_parity.py) and [edit-stage coverage](edit-localization.md). Live sampling and upstream prompt, sampling/merge and error-handling parity remain unfinished. |
| Repair prompt | Published Python `--cot --diff_format` prompt | Prompt construction for that configuration | [Prompt test](../tests/test_repair_prompt.py). Does not establish parity for every upstream prompt option. |
| Applying model edits | The pinned repair postprocessor uses the first selected file | All accepted SEARCH/REPLACE edits are applied atomically across existing files | [Edit tests](../tests/test_repair_edits.py). This expands repair capability and changes rejection behavior; it is a disclosed difference. |
| Voting key | Python AST-based normalization of source, including comment/docstring handling | Textual diff normalization that retains context and hunk locations | [Patch tests](../tests/test_patch_and_selection.py). Voting groups can differ from upstream; normalization parity is not established. |
| Selection | Regression filtering, reproduction preference with fallback, then voting | Same intended ordering and first-appearance tie-break; infrastructure failures are excluded | [Selection tests](../tests/test_patch_and_selection.py) test local policy. They are not an upstream differential test of all edge cases. |
| Tests used for selection | Regression-test selection and reproduction-test generation, followed by execution | Fixed schedules or recorded regression exclusions; one recorded generated reproduction source can be checked on baseline and candidates with a trusted command | [Regression selection](regression-selection.md), [reproduction tests](reproduction-tests.md) and [validation note](public-validation.md). Automatic discovery, framework reports, live generation, multiple generated tests and upstream marker-protocol parity remain unfinished. |
| Docker execution | Existing Docker/SWE-bench test infrastructure | Local `DockerTestRunner` executes commands in disposable containers | [Runner tests](../tests/test_docker_validation.py). This reimplements an execution mechanism; it introduces no new Agentless stage. |
| Benchmark integration | Original SWE-bench task and harness conventions | Projected SWE-bench Pro input records and three recorded Python smoke tasks | [Dataset tests](../tests/test_swe_bench_pro_dataset.py), [smoke inputs](../experiments/swe_bench_pro/python_smoke_set.json). Official scoring and DeepSWE integration remain unfinished. |
| Language support | Python-specific implementation | Python, Go, JavaScript, TypeScript and Rust adapters selected by the controller | [Go support](go-adapter.md), [JavaScript/TypeScript support](javascript-typescript.md) and [Rust support](rust-adapter.md) cover controlled recorded workflows and optional runtime checks. Real multilingual benchmark coverage remains untested. |

The relevant upstream sources are
[repair.py](https://github.com/OpenAutoCoder/Agentless/blob/b150f28465a77a81a7f4776384957a4271f5bd69/agentless/repair/repair.py),
[rerank.py](https://github.com/OpenAutoCoder/Agentless/blob/b150f28465a77a81a7f4776384957a4271f5bd69/agentless/repair/rerank.py),
[postprocess_data.py](https://github.com/OpenAutoCoder/Agentless/blob/b150f28465a77a81a7f4776384957a4271f5bd69/agentless/util/postprocess_data.py),
and [run_tests.py](https://github.com/OpenAutoCoder/Agentless/blob/b150f28465a77a81a7f4776384957a4271f5bd69/agentless/test/run_tests.py).

## Reasons and trade-offs

### Separate implementation and reference

A pinned, unchanged reference lets us distinguish upstream behavior from our
changes. Extending the original repository directly would reuse more code, but
would require maintaining a separate reference anyway to measure differences.
The cost is maintaining more code and checking that we have not accidentally
changed the method. The fixtures help, but they cover only part of that comparison.
See [ADR 0001](adr/0001-separate-generalized-baseline.md).

### Language-specific structure behind a common workflow

We want to add a language without copying the controller or scattering language
checks through it. Adapters give parsing code a clear home. The design is still
provisional: all five initial languages now exercise it, but more varied source
and real repositories may expose further changes needed in the representation.
See [ADR 0002](adr/0002-language-adapter-boundary.md).

### Recorded responses during development

Saved responses let us repeat a failure with exactly the same inputs. They also
make it easy to test malformed responses and competing patches without model calls.
A live model would change those inputs between runs. We will connect one later;
for now, the controller accepts `RecordedStageResponses`. These tests tell us
whether the code handles the supplied responses, not whether a model would produce
a useful repair.

### Independent candidate checkouts

Every candidate starts from the same pinned repository revision. Fresh checkouts
avoid depending on a reset procedure to remove files or state left by an earlier
candidate. Reusing and thoroughly resetting a checkout could be faster, but would
require checking that the reset removes everything the previous candidate left
behind. Fresh checkouts are the simpler option for now, at the cost of extra work
per candidate. See [workspaces](workspaces.md).

### Docker command runner

The runner gave the recorded controller a way to execute tests and collect outcomes.
Upstream Agentless already performs Docker-backed patch validation. Reusing its
runner would require adapting its SWE-bench-specific inputs; the current generic
runner instead accepts an image and commands. That convenience has limits: it
counts command outcomes, not individual failed tests, and its filesystem and
resource restrictions can affect execution. Using an official image alone does
not reproduce an official harness. Full benchmark integration must check these
differences and reuse the official execution/scoring mechanisms where appropriate.

### Reading only the benchmark fields we need

The SWE-bench Pro loader reads only approved input columns because full rows also
contain solution and verifier data. Loading everything and deleting fields later
would make every intermediate record another place to check for accidental use.
The loader checks the dataset fields only. Container contents and supplied test
commands still need a separate review for solution or verifier information.
See [the benchmark note](swe-bench-pro.md).

### Multi-file edits and textual normalization

Multi-file application supports repairs that span files, but can accept repairs the
pinned upstream postprocessor would not produce. It therefore affects capability,
even with the same fixed controller. File creation and deletion remain unsupported.

Textual normalization avoids a Python-only AST requirement in the common repair
code. It is provisional: it can group patches differently from upstream, and
whitespace normalization is not a proof of semantic equivalence. Retaining upstream
Python normalization behind a language adapter is an alternative to evaluate.
Any resulting change in voting must be documented before experiments.

Majority voting itself is inherited: it is a heuristic when available test evidence
cannot distinguish candidates. More votes do not prove correctness. First appearance
resolves ties reproducibly; it supplies no additional correctness evidence.

## How to maintain this record

For a consequential change, record the problem, chosen behavior, a plausible
alternative, the trade-off, and the evidence available. Label untested reasoning
as provisional. Do not invent a historical rationale when the reason is unknown;
record it as a decision that still needs review.

Keep inherited method choices tied to the upstream source. Record changes to
model-visible context, candidate eligibility, voting, or test evidence even when
they originated as implementation conveniences. Tests of local behavior and
comparisons against upstream support different claims and should be identified
separately.
