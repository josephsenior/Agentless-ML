# Testem: exact QUnit 2.9.2 assets and the unchanged todo test

The unchanged `ci mode app::handles todos correctly` public test passed in
**18.093 seconds**, exit code 0. Only that test ran. No full-suite retry has
started, and canonical readiness remains **100/113**.

## What was missing

The previous full schedule's remaining failure came from the public todo
fixture, which explicitly requests QUnit 2.9.2 rather than 1.20.0. We kept both
versions: substituting one for the other would change what the fixture tests.

The [publisher index](https://releases.jquery.com/qunit/) lists both 2.9.2
files. Its JavaScript SRI matches the downloaded bytes. Both CDN files also
match the upstream files byte-for-byte at tag commit
`0f727f13fb09ccefd9fa83cfe85424e938604aad`:

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| qunit-2.9.2.js | 188837 | `110e6bbfa90f14f29051863e3f81fa7e6fe57bec8544b5406ffff63df06cc1f1` |
| qunit-2.9.2.css | 7875 | `b687a939ee43f9d757814386b228e78729999dae5b6a4274830442ff76cad5bd` |

The CSS has no publisher SRI and no additional `url(...)` dependencies. Its
hash was computed locally and checked against the exact upstream bytes. This
is HTTPS/SRI and immutable-commit verification, not a signed-release audit.
The [manifest](../experiments/deepswe/testem_qunit_2_9_2_assets_verified_2026_10_10.json)
records the URLs, hashes and verification-stage facts.

## Separate environment, same test

The offline build produced `agentless-ml/testem-offline-qunit-todo:2026-10-10`,
image `sha256:e12cec1885154964e390345726e5ae53955831965fc1340f1cd5b9f11220328f`,
from the preceding 1.20-only diagnostic image. That older image and its records
remain intact. The new service inherits the old delivery logic and adds only
the two exact 2.9.2 routes. All four files are rehashed before serving.
Nothing proxies to the internet, rewrites tests or fabricates outcomes.

All **13 native HTTP checks** passed: GET/HEAD for four assets plus rejection
of unknown paths, favicon, wrong host, query strings and POST. The subsequent
single-test run used the sealed base revision
`158f61ea91c9613d2011c41ee9be40ada1d7a307` and the existing HOME-only setting.
The diagnostic observer records the original reporter calls and returns;
it does not replace their decisions. Test source, assertions, browser arguments,
report parsing and the 1,800-second cap were unchanged.

The browser reported the fixture's intentionally failing todo and unexpectedly
passing todo. Testem counted two total, zero passing, zero skipped and one todo;
its own `hasPassed()` correctly returned false for this deliberately failing
fixture. The outer Mocha test **passed**, because it checks that this behavior
is reported correctly. We did not turn the fixture's intentional failure into
a success. Service logs show the exact 2.9.2 JS/CSS delivered with HTTP 200.

Docker inspection confirmed network=none, read-only root, cap-drop=ALL,
no-new-privileges, no privileged mode, 8 GiB memory with no extra swap,
two CPUs, 2,048 PIDs and the same 4 GiB executable/nosuid/nodev /tmp.
Only code.jquery.com is mapped to container loopback; no port is published.
The owned containers were removed and the scoped host keep-awake request released.
Thirteen focused host checks passed before execution; the expanded final check
passed all 17 tests. These are separate from benchmark tests.

## Reproduce and evidence

With `PYTHONPATH=src`, the opt-in commands are:

```text
python tools/verify_testem_qunit_assets.py --version 2.9.2
python tools/testem_qunit_todo.py build
python tools/testem_qunit_todo.py preflight
python tools/testem_qunit_todo.py test
```

Capture directories and image tags intentionally refuse overwrite during
verification/build. Existing captures and pinned images can be used for the
later commands. This entry point exposes no full-suite option.

The [compact evidence](../experiments/deepswe/testem_qunit_todo_public_test_2026_10_10.json)
contains build identity, preflight checks, inspected protections, reporter
observations, delivered hashes and the actual single-test result. Raw logs,
execution record and xUnit report are under
`../output/deepswe-survey/testem-offline-qunit-todo/public-test-logs/agentless-ml-a8e2f24662c74ba2bb608515f44ae8c1/`.
Public asset captures and build/preflight logs are in the adjacent audit and
image directories. No held-out tests or solutions were used.

Next: request one unchanged full public schedule in this four-asset condition.
A passing targeted test does not yet establish that the full schedule passes.
No further retry or canonical survey update was started. KGateway, Numba and
Pwntools remain parked.
