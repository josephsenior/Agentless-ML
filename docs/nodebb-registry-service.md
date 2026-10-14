# NodeBB registry snapshot service

The separate image `agentless-ml/nodebb-registry-snapshot:2026-10-14` adds the
four [reviewed public snapshots](nodebb-registry-assessment.md) and a small Node
HTTP service to the pinned NodeBB image. Its immutable ID is
`sha256:3b4a66b46fa2aa2cc821870fbd9c8a0bd9ec12dae99aaf5449307c7c77ebdf0e`.
The builder verifies the original parent ID and confirms that all its filesystem
layers remain the supplemented image's prefix. Snapshot hashes are checked
before building and again when the service starts.

The image label names the condition: "NodeBB registry snapshot diagnostic,
captured 2026-10-14". It keeps this current-data supplement identifiable in
later results. The historical published-image attempts remain separate.

## Delivery verification

The service binds to `127.0.0.1:8766` inside the same container as NodeBB and
Redis. GET serves each captured body unchanged; HEAD returns its length without
a body. Unknown paths, plugin IDs and version queries return 404. Unsupported
methods, including the usage telemetry POST, return 405. Requests and body
hashes are logged. The service makes no upstream requests.

`tools/run_nodebb_registry_page.py --verify-only` passed in the supplemented
image with the existing offline container protections. All four GET bodies
matched the manifest's SHA-256 and byte count, all four HEAD checks passed,
and the four negative request checks returned their expected failures. The
local build and delivery evidence is under:

- `../output/swe-bench-pro-v2-readiness/2026-10-14-nodebb-registry-image-v2/`
- `../output/swe-bench-pro-v2-readiness/2026-10-14-nodebb-registry-delivery/`

## Public page replay

The normal Redis bootstrap still generates configuration and assets from the
candidate checkout. The wrapper adds the supported configuration value
`registry: "http://127.0.0.1:8766"` before Mocha starts. CPU, memory, temporary
storage, network restrictions and the repository's test settings stay as in the
previous public run. No host ports are published.

The page's assertions come from `test/api.js`, which generates groups of seven
cases for each Read API route. These cases share display names rather than
including their route. The replay runs that unchanged public file through the
normal NYC/Mocha command. It derives the admin plugins page's occurrence number
from `public/openapi/read.yaml` using the same path order as the test generator,
then checks all seven original assertion outcomes for that occurrence. Source
hashes and both raw and distinct-case reports are retained. Other API-file
outcomes remain visible; this replay does not establish full-suite readiness.

## Result on 14 October 2026

All seven admin plugins page assertions passed, including the HTTP status and
response-schema checks that previously stopped the run. The complete public
API file passed **2,496 individual cases**. Its completion audit accounts for
all 2,496 registered tests, including 2,495 added after Mocha started. There
were no missing cases or hook failures. The command exited 0 and took 213.27
seconds including runner preparation.

The service log confirms that NodeBB requested compatible, full and trending
plugin data and received the exact captured bodies. The separate delivery
check also verified the Markdown detail response and unsupported-route errors.
See the [saved image and replay evidence](../experiments/swe_bench_pro/v2_js_nodebb_upload_path/registry-service-replay-2026-10-14.json)
for source hashes, all seven page outcomes and artifact digests.

An earlier preparation was interrupted before test execution; it produced no
test artifacts. The successful replay used a new output directory and durable
host logs. Its normal container/workspace cleanup completed, and the earlier
disposable checkout was removed after its ownership and base were verified.
Pinned source repositories and reports were preserved.

## Full public suite attempts

The wrapper now accepts `--full-suite`. A focused command check verifies that
this mode removes only the API-file selection from the same registry setup;
the normal `npm test` file discovery and public bail setting remain active.

The first full attempt passed 2,195 cases, then failed ActivityPub's local-user
URL resolution. The public setup uses an HTTP URL. At the pinned base,
`src/activitypub/index.js` allows HTTP only when `process.env.CI === 'true'`;
the wrapper had omitted that CI setting. Its
[original evidence](../experiments/swe_bench_pro/v2_js_nodebb_upload_path/registry-full-without-ci-2026-10-14.json)
is retained. The wrapper now exports `CI=true` for both replay modes, preserving
the public HTTP configuration and the original image, limits and test source.

The full retry with that setting passed the earlier ActivityPub assertion and
reached **3,321 passes and one failure** in 298.74 seconds including runner
preparation. The failure is the public test
`Plugins install/activate/uninstall should install a plugin`: its normal
`npm install nodebb-plugin-imgur@1.0.16 --save` returned `ENOTCACHED` because
the required npm registry metadata was absent from `/tmp/npm-cache` while
offline. The service still verified its response hashes and all seven admin
plugins page assertions passed.

The completion audit recorded 7,986 registered tests and 3,322 ended tests;
4,664 did not run after the failure. Raw and distinct-case reports agree.
NodeBB therefore remains **not ready** for a complete public baseline. See the
[full-run evidence](../experiments/swe_bench_pro/v2_js_nodebb_upload_path/registry-full-public-2026-10-14.json)
for the failure, counts, configuration and artifact hashes. Both attempts
completed normal container and workspace cleanup.

Update: further snapshot/cache work is paused. The
[network policy review](network-policy.md) separates offline agent execution
from connected trusted setup and unchanged-base diagnostics. The previous
service and runs below remain labelled historical evidence, not a required
setup for every future run.

The [Imgur assessment](nodebb-imgur-assessment.md) now verifies the old install
and current upgrade targets: 56 unique packages across both isolated trees,
plus the public NodeBB detail response. That response agrees with the earlier
full-list snapshot and the public test's expected registry fields. Merely
caching those tarballs still does not prove the full NodeBB-root
`npm install --save`, upgrade and uninstall transactions can finish. The former
next step was to assess root cache coverage and writable dependency layout;
that cache work is now paused in favour of the phase-specific network review.
No cache image or further full-suite retry has been started.
