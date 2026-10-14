# Public registry data for NodeBB's offline tests

The four reviewed registry responses can be captured and served locally through
NodeBB's existing `registry` setting. This assessment supports building a
labelled snapshot diagnostic. It does not establish that the complete public
suite will finish or that the captured data reproduces the historical registry.

## Verified public responses

On 14 October 2026, all four HTTPS requests to `packages.nodebb.org` returned
HTTP 200 and `application/json`. `tools/assess_nodebb_registry.py` checked the
response shapes, recorded dates and ETags, calculated SHA-256 hashes, and
rechecked the saved bytes. The complete metadata and pins are in the
[snapshot manifest](../experiments/swe_bench_pro/v2_js_nodebb_upload_path/registry-snapshots-2026-10-14.json).

| Request path | Public data | Captured size |
| --- | --- | --- |
| `/api/v1/plugins?version=4.1.0` | 215 compatible plugins | 56,548 bytes |
| `/api/v1/plugins` | 1,793 plugins | 432,396 bytes |
| `/api/v1/analytics/top/week` | 10 trending entries | 513 bytes |
| `/api/v1/plugins/nodebb-plugin-markdown` | Markdown plugin details | 2,291 bytes |

Every compatible plugin and trending label appears in the full list. The full
list contains no duplicate names. The Markdown detail and full-list responses
both name version `13.2.13` as latest. Snapshot bodies remain unchanged in
`../output/swe-bench-pro-v2-readiness/2026-10-14-nodebb-registry-assessment-v2/`.

These hashes pin our captures. They are not upstream-published checksums or
signatures. HTTPS authenticates the source, and the saved hashes support exact
local replay. The lists, latest versions and weekly rankings are current data;
there is no evidence that they match the task's original date. A supplemented
condition must therefore identify the capture date and manifest hash.

## Why these routes

The pinned `src/controllers/admin/plugins.js` requests compatible, all and
trending data together. `src/plugins/index.js` reads all three paths from
`nconf.get('registry')`, falling back to the public host. Its `Plugins.get`
also requests a plugin detail path; the existing `test/plugins.js` calls that
method for `nodebb-plugin-markdown`. The public test database helper reads
`config.json`, so the supported setting can be added to generated configuration
before Mocha starts, without changing application or test source.

The same registry setting is used for optional usage telemetry at
`POST /api/v1/plugin/usage`. This assessment captures no write-response data.
That route must remain unsupported, with attempted requests recorded. Do not
invent successful acknowledgements. Other unknown plugin IDs or query versions
also need explicit failures until their actual public responses are reviewed.

## Proposed diagnostic

Use a small service bound to `127.0.0.1:8766` inside the test container and set
the generated configuration's `registry` to `http://127.0.0.1:8766`. Replay
the original JSON bytes for the four exact paths and queries. Verify each file's
hash before startup; retain request logs and the capture manifest. Unsupported
routes must fail explicitly. GET and HEAD are sufficient for the reviewed data.

The service can use the pinned image's existing Node runtime. Keep the current
container network disabled, publish no host ports, and retain the same CPU,
memory, scratch and test settings. Redis remains on port 6379 and NodeBB on
4567. This setup would cover the reviewed registry requests; it does not supply
arbitrary internet access or prove coverage of later external dependencies.

Next, build the labelled supplemented setup and verify byte-for-byte delivery
and unknown-route failures. Then run the unchanged admin plugins page test
against it before considering another complete schedule. No service has been
built, no tests retried, and NodeBB remains unready after this assessment.
