# Cliffy: cache registration and official readiness refresh

Cliffy is now **ready** in the official survey. The fresh unchanged full Deno
schedule passed: **878 normalized regression IDs, zero failures or skips**,
exit code 0. Execution took 65.093 seconds; the survey recorded 68.5 seconds
including setup and cleanup.

Overall readiness is **102/113**, with 11 tasks remaining: 100 ready in their
published pinned images and two ready in explicitly registered modified
environments (Testem and Cliffy). This is infrastructure readiness, not a
benchmark solve rate or a claim that the original Cliffy image now works.

## Registration review

The local image still matches the earlier offline graph and full-baseline
evidence: `sha256:9e49eb0e15b12e2fbded70acbcb9a4f0948bbdbc731539299e0e99bd68ff27c9`.
Its parent is the unchanged published pin
`sha256:0a8dd8f1270ec4bb88efadad3021762e1d07274f686276c8a484d26a00bd91b5`.
Docker inspection confirmed the parent layers remain and the image's
environment and configured user are unchanged. No rebuild or download was needed.

We rehashed all **1,067 saved dependency artifacts**, totaling 4,994,584 bytes,
against the reviewed manifest. These cover package/version metadata plus
**1,011 source files across 29 package/version records**. The manifest SHA-256,
`2ca1b8999c367e7fd581e189fb7f2713b85404c866c120ae971a735c58d72be6`,
matches the build and successful offline graph record. Deno remains 2.0.0;
the build adds absent cache entries without replacing original ones or source.

The [registry](../experiments/deepswe/environments.json) now binds this image to
Cliffy's exact base `132a437c40cffbdfbe474ca808c8debde59e2633`, original image
pin, reviewed manifest/graph evidence and passing full public baseline. The
loader rejects mismatched images, task pins, evidence and manifest hashes.
The original `corpus_pin.json` and historical assessment records are unchanged.

This cache is curated: added package indexes expose only the reviewed versions.
It is **not a reconstruction of historical upstream dependency resolution or
a new lockfile**. The fixed image and that limitation must remain explicit
in the experiment protocol. Registration does not erase the distinction.

## Image-only execution

The shared survey, public-test and recorded-workflow tools select this
registration by default for Cliffy. Unlike Testem, Cliffy needs no service,
hostname mapping, HOME prefix or command supervisor. Its public Deno command
is returned unchanged, including default full discovery, `--cached-only`,
permissions, parallel mode, JUnit report and the 1,800-second cap. No selector,
exclusion, source edit or changed assertion was introduced.

The image-only runner observes Docker protections without changing arguments.
The official run confirmed network=none, read-only root, cap-drop=ALL,
no-new-privileges, 8 GiB memory with no extra swap, two CPUs, 2,048 PIDs,
the same 4 GiB executable/nosuid/nodev /tmp, no privileged mode, no added host
mapping and no published ports. The owned container was removed and scoped
Windows keep-awake request released. No persistent power setting changed.

## Counts and evidence

Native Deno output reports **822 tests and 76 steps passed**. Raw XML has
898 passing entries. Existing duplicate-label normalization produces 878
regression IDs; no counting rule changed and no twenty tests were excluded.
The 51 focused host checks passed, including unchanged Deno command identity,
image-only runner dispatch, rejection of mismatched evidence and continued
Testem behavior. These checks are separate from benchmark tests.

Only Cliffy was rerun and appended to `../output/deepswe-survey/survey.jsonl`.
The latest outcomes are 102 ready, five unsupported repositories, three
harness errors, two out-of-memory outcomes and one timeout. The
[committed refresh record](../experiments/deepswe/cliffy_registered_readiness_2026_10_10.json)
keeps the review, prior/fresh Cliffy records, remaining tasks, protections and
report digest. Raw artifacts are under
`../output/deepswe-survey/runs/cliffy-config-file-parsing/logs/agentless-ml-29a5344124f546cfba12aa6d0a3a8b65/`.

With the project virtual environment and `PYTHONPATH=src`:

```text
python tools/survey_deepswe.py --tasks-root ../benchmarks/deepswe/corpus/tasks --repositories ../benchmarks/deepswe/repos --task-id cliffy-config-file-parsing --rerun --results ../output/deepswe-survey/survey.jsonl --artifacts ../output/deepswe-survey/runs --timeout-seconds 1800 --tmpfs-mb 4096
```

The held-out scorer and its environment are unchanged. No hidden tests or
solutions were read, no model was called and no further retry has started.
Next: review GoReleaser's already verified cache-relocation image for an
explicit registration. Numba, KGateway and Pwntools remain parked.
