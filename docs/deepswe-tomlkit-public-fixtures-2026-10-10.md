# Tomlkit: verified public fixture setup

Tomlkit's full public baseline passed: **964 passed, zero failures or skips,
exit 0**. Readiness is now **105/113**, with eight tasks remaining: 102 tasks
use their original published images and three use registered modified images.
Tomlkit is in the original-image group.

## Why the submodule matters here

The old survey stopped at the workspace provider's now-obsolete submodule
refusal. Unlike Adaptix's performance data, Tomlkit's `tests/toml-test` is read
by its normal public suite. `tests/test_toml_tests.py` opens
`tests/toml-test/tests/files-toml-1.1.0` during collection, then loads the listed
TOML and expected JSON files. Public CI checks out submodules recursively.

The sealed host checkout leaves that submodule uninitialized. The published
image already contains exactly its pinned revision, so no network fetch or
supplemented image is needed.

## Pins and verification

- Task: `tomlkit-toml-table-converters`.
- Base: `dd05eebc8ed9e30fc6c223088a5a450cb54c1cab`.
- Original image: `sha256:0785d2c9caa62130352713828a2a98f85b991f87fa853bad7252546df9ff0eec`.
- Public submodule commit: `08ed8697864548b3cdb4b8decbf496bef47e1c82`.
- Submodule tree: `4b9ff71fa2de930104473805a662117f5b38ea87`.
- Complete tracked manifest SHA-256:
  `00968accf894aefccffc2d3c47c2c78a3f9a06a21f4b62c3a3f5c0d9c2bd7055`.

The earlier offline inspection verified the commit and root-tree object hashes,
all 1,042 tracked files (327,503 bytes) against their Git blobs, the complete
fixture list, and a clean submodule status in the image.

The permanent setup rechecks the exact commit and all tracked-file bytes against
Git blob IDs, then checks the pinned SHA-256 manifest before writing anything.
Manifest encoding is compact JSON with sorted keys, ASCII escapes and Git
`ls-tree -rz` order; each entry has path, mode, Git blob ID, byte count and SHA-256.
It ignores untracked files rather than copying them.

## What enters the candidate

Only **895 regular data files, 135,761 bytes** enter
`/tmp/work/tests/toml-test`: the public index plus its 894 referenced TOML/JSON
files. The selected-manifest SHA-256 is
`cd516b79b2cbc2895f371692bcdfb7b52946f77db94a07320c1e56b6a437b8ea`.
The index lists 680 TOML cases and 214 JSON expectations; it is not 894 tests.

No image Python implementation, image test module, documentation, executable
tool or `.git` metadata is copied. The setup rejects a nonempty destination,
symlink paths, unsafe fixture references, mismatched commits/blobs/manifests and
missing referenced files. It writes exclusively and rechecks destination hashes.
The host repository remains unchanged with its submodule uninitialized; this
provisioning happens only inside each disposable candidate container.

The `tomlkit-pytest` override is shared by survey, standalone test tool and workflow.
It checks that `tomlkit` imports from `/tmp/work/tomlkit`, then runs the existing
default pytest command with the same configuration, assertions, report flags
and target forwarding. A setup failure exits 125 before tests. Generic pytest
and the held-out scorer are unchanged.

## Result and safeguards

The fresh result includes **214 valid decode, 452 invalid decode and 14 invalid
encoding cases** from the submodule (680 total), plus 284 other public tests.
All passed, with no address-bearing Python repr IDs observed. Execution took
6.841 seconds and survey preparation/cleanup brought the attempt to 8.5 seconds.

The existing offline/read-only Docker runner and limits are unchanged: 1,800
seconds, 8,192 MiB memory with no extra swap, two CPUs, 2,048 PIDs and 4,096 MiB
temporary storage; all capabilities dropped and no-new-privileges retained.
No test was filtered or modified. The owned container was removed afterward.

Host verification: **145 passed, five skipped**. Tests cover data-only copying,
exact binary content, wrong commit/manifest, modified fixture or nonfixture
files, refusing candidate overwrites, unsafe paths, import provenance and command
preservation. One real directory-symlink check was skipped because Windows
denied creating it; the other four skips are opt-in delegated-runner checks.

The official append-only survey is `../output/deepswe-survey/survey.jsonl`.
Artifacts are under
`../output/deepswe-survey/runs/tomlkit-toml-table-converters/logs/agentless-ml-079f0cb6dd924ee19ba4f74951bf3fb4/`.
The [committed record](../experiments/deepswe/tomlkit_public_fixtures_2026_10_10.json)
retains pins, hashes, counts and remaining task statuses.
