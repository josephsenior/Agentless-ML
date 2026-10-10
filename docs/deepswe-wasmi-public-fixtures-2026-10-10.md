# Wasmi: verified public WAST fixture setup

The fresh official baseline passed: **791 passed, zero failures or skips,
exit 0**. Readiness is **106/113**, with seven tasks remaining: 103 original-image
tasks and three registered modified environments. Wasmi uses its original image.

## Why these files are needed

The old survey rejected all submodules before testing. The current workspace
provider leaves them uninitialized, but `crates/wast/tests/mod.rs` embeds public
WAST data from `spec` and `wasmi` with `include_str!`. Both fixture sets are needed
at compilation time. The third submodule, `crates/wasmi/benches/rust`, is for
benchmarks and is not needed by the existing default nextest schedule.

The setup reads the literal fixture declarations from the image's pinned Git
object, then verifies their exact selected-file manifests. Candidate-controlled
requests cannot enlarge the copied set. Candidate Rust source and public Rust
test code remain the streamed checkout's files; none are copied from `/app`.

## Verified pins

- Base: `e1f76e285b9ad68a952b7cf5297bbb7ab91e6028`.
- Original image: `sha256:1bec57bc662b5c33289f88cb28cae2c4df07cb33cd96aff7840c77e2b0a96c10`.
- `spec`: `d76759e746f3564a03f6106ae19679742f2a1831`, 452 tracked files verified;
  212 referenced WAST files supplied (10,929,985 bytes).
- `wasmi`: `60701c2664b235ec07ca0231c32a1764dbce4f23`, 257 tracked files verified;
  140 referenced WAST files supplied (1,439,057 bytes).

The earlier offline inspection checked both commit/root-tree object hashes,
every tracked file against its Git blob, clean submodule status, and the presence
and UTF-8 content of all referenced WAST files. Permanent setup rechecks the
image base, both submodule commits, Git blob hashes and pinned SHA-256 manifests.
It verifies both sources and both selected sets before any copy begins.

The [evidence record](../experiments/deepswe/wasmi_public_fixtures_2026_10_10.json)
retains all four manifest hashes. Encoding is compact JSON with sorted keys,
ASCII escapes and Git `ls-tree -rz` order; each entry contains path, mode,
Git blob ID, byte count and SHA-256.

Only the **352 allowlisted regular `.wast` files**, 12,369,042 bytes total, enter
the two empty candidate submodule directories. No Git metadata, Rust source,
unused WAST files, docs, benchmark inputs or image-built artifacts are copied.
The setup rejects nonempty destinations, symlinks, unsafe paths, missing required
files and mismatched commits/blobs/manifests. It writes exclusively and verifies
copied bytes again. A setup failure exits 125 before Cargo runs. All three host
submodules remain uninitialized; provisioning is inside the disposable container.

## What ran

The task-specific `wasmi-cargo-nextest` override is shared by survey, standalone
public-test tool and workflow. It adds provisioning before the existing Cargo
command, retaining workspace/default feature selection, target forwarding,
nextest flags, failure exit code 100, report path and caller deadline. No package
filter, all-features expansion or benchmark target was added. This is the
existing nextest public schedule, not the repository's complete CI matrix or
Cargo doctest schedule.

All 791 report IDs passed: `wasmi` 111, `wasmi_cli` 10, `wasmi_collections` 13,
`wasmi_core` 21, `wasmi_ir` 1, `wasmi_wasi` 2 and `wasmi_wast` 633. The WAST cases
run in several configurations, so 352 input files do not imply 352 test IDs.
Execution took 108.577 seconds; the survey attempt took 112.9 seconds.

Unchanged protections: offline network, read-only root, all capabilities dropped,
no-new-privileges, no privileged mode, added hosts or published ports; 8,192 MiB
memory/no extra swap, two CPUs, 2,048 PIDs, 4,096 MiB temporary storage and a
1,800-second cap. Live container inspection confirmed these settings. The
ordinary survey's `docker_protections` field remains null for original-image
tasks. A temporary Windows keep-awake request was active only for this attempt
and released afterward; the owned container was removed.

Host checks across two focused groups: **159 passed, five skipped**. They cover
exact allowlist copying, wrong base/commit/manifests, changed fixture/nonfixture
bytes, refusing occupied destinations, verifying both sources before any copy,
unsafe paths and preservation of the existing nextest command. Skips were four
opt-in delegated-runner checks and Tomlkit's host-restricted symlink test.

The append-only official survey is `../output/deepswe-survey/survey.jsonl`.
Artifacts are under
`../output/deepswe-survey/runs/wasmi-trap-coredumps/logs/agentless-ml-a2fb333e4cb64efead4877d5485b43f6/`.
