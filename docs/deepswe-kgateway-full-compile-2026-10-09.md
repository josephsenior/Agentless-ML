# KGateway: full compile attempt interrupted by a host pause

The approved single-worker compile attempt did not produce a usable full-build
result. A **4,620.17-second monitoring gap** occurred between samples at 52.29
and 4,672.46 seconds, consistent with host suspension. Compilation resumed
afterwards, but this is not an uninterrupted 30-minute attempt.

The runner retained its existing 1,800-second timeout. That timeout did not
terminate the process across the observed pause. Once the gap was discovered,
we issued `docker stop --time 1` against this attempt's exact owned container;
the runner ultimately recorded `timeout`, with no exit code, after 4,791.1
seconds including setup and cleanup. The timeout result and the stop occurred
around the same end of execution; this is not evidence of 30 minutes of active
compilation or a demonstrated full-build resource failure.

## Unchanged condition

The command was:

```sh
GOCACHE=/tmp/go-build GOTMPDIR=/tmp/compile-work \
  go test -c -p 1 -o /dev/null ./...
```

This uses the same pinned KGateway image and sealed base as the
[short check](deepswe-kgateway-compile-diagnostic-2026-10-09.md), a fresh cold
cache, all packages, one build worker and no test execution. The five-minute
inner timeout was removed only for the explicitly requested full attempt;
the existing outer timeout remained 1,800 seconds. Limits remained 8 GiB memory,
two CPUs, 4 GiB scratch and 2,048 PIDs. Docker inspection confirmed no network,
read-only root, dropped capabilities and no-new-privileges.

## What the samples establish

There are 13 resource samples. The final sample at 4,733.98 seconds reports:

- Scratch: **1,702,023,168 bytes (1.59 GiB)**, the highest sampled value.
- Cgroup memory peak: **1,925,304,320 bytes (1.79 GiB)**.
- No OOM or OOM-kill events; no space error in the sampled stderr tails.
- Cumulative cgroup CPU use: about **179.9 CPU-seconds**.

The small CPU total and slowly advancing build state are consistent with a
pause rather than thousands of seconds of active compilation, but do not
identify its cause. There is no resource coverage inside the long gap or at
the final stop. The retained stdout/stderr logs are empty; progress survives
only in resource probes. Do not infer full stderr coverage or a final peak.

This run cannot establish whether the complete build fits. No tests executed,
no regression inventory was accepted, no survey was updated and no retry was
started. Canonical readiness stays **100/113**. The owned container was removed.

Raw evidence:
`../output/deepswe-survey/kgateway-compile-diagnostic/logs/agentless-ml-89669a5282674adca220910c647ba8da/`.

The next useful check would be the same single attempt on an uninterrupted
host, with sleep disabled for the window. It requires another explicit go-ahead;
this interruption does not authorize an automatic repeat or larger limits.
