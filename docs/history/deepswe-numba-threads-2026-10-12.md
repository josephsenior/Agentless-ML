# Numba thread inspection under the two-CPU quota

> Development record. See [the documentation guide](../README.md) for current status.

Configuration and discovery probes used the existing pinned Numba image with
8 GiB RAM, two CPUs, disk-backed `/tmp`, Docker-default swap and the normal
offline protections. No test bodies ran and no full baseline was retried.
The anonymous probe containers and volumes were removed automatically.

Docker's CPU quota was `200000 100000`: two CPUs' worth of execution time.
However, both CPU affinity and `os.cpu_count()` exposed 16 CPUs. The pinned
`numba/core/config.py:492` uses affinity to choose its default thread count,
so Numba configured 16 threads and selected OpenMP. No thread environment
variables were set in the image.

After importing NumPy and SciPy, both loaded OpenBLAS libraries reported
16 threads, and the process had 31 OS threads. Limiting the BLAS pools to one
thread left one OS thread after those imports. Numba still reported its
16-thread maximum and mask; reading that mask does not measure concurrent
execution of a compiled parallel kernel.

The image's config and `test_num_threads.py` exactly matched the sealed
repository files by SHA-256:

- config: `dcf8f320d8f09885880e4dba3ac6ad6667d060b72f8ad73ea5a03fd39758bbd3`
- thread tests: `669b915758437cd62a4ad5d967ea419093fef08cfb40a1e3793bc99f50f23ccc`

## Why only change OpenBLAS

Native discovery (`python /app/runtests.py -l`) in the pinned image produced:

| Environment | Discovered IDs | Change from default |
| --- | ---: | --- |
| Image defaults | 10,609 | none |
| `OPENBLAS_NUM_THREADS=1` | 10,609 | identical sorted ID list |
| Above plus `NUMBA_NUM_THREADS=2` | 10,492 | 117 cases removed |

The default and BLAS-only inventories share SHA-256
`59aa80f188ea28d2613896585bca9b3ff0ea3c32f1a1562da2ecb84f55be0bc2`.
Every removed ID belongs to `TestNumThreadsBackends`, whose generator at
`numba/tests/test_num_threads.py:586` uses the configured Numba maximum to
choose the 1/2/4/8/16-thread variants. That family shrank from 195 to 78 cases.
Lowering Numba's maximum can also trigger its hardware-dependent skip guards.
These discovery results inspect the image's existing public source; they are
not candidate-validation outcomes or a completed regression inventory.

The registered public Numba command now exports `OPENBLAS_NUM_THREADS=1`
before building or importing Python code. Its children inherit the setting.
It leaves Numba's maximum, the native serial runner, test targets, assertions,
candidate-source build, image and task limits unchanged. The survey,
single-task command and workflow share this command template.

The visible CPU count and default BLAS pools establish an oversubscription
risk, not how much it contributed to the earlier timeout. The earlier full
run used the old BLAS defaults. No speed improvement or full-suite completion
has been measured for the new setting; Numba remains unready and the latest
public-baseline count stays **112/113**.

The subsequent [short timing diagnostic](deepswe-numba-blas-diagnostic-2026-10-12.md)
reached at least 425 completions before its deliberate cutoff, without a full
report or readiness change. Use an explicit worker count for
any parallel diagnostic: bare `-m` defaults to the visible CPU count, which
would select 16 workers despite the two-CPU quota. The upstream CI also uses
sharding and excludes long-running tests; those exclusions are not adopted
by this full-schedule baseline.
