# Testem: verified QUnit assets and offline-delivery assessment

Both exact QUnit 1.20.0 assets are available and verified. A narrowly labelled
loopback HTTP service is feasible without external connectivity, test edits or
Docker protection changes. **No service image was built, no listener started
and no benchmark test was run in this assessment.**

## Verified public bytes

The pinned public template references `/qunit/qunit-1.20.0.js` and
`/qunit/qunit-1.20.0.css` at code.jquery.com. They were acquired on the host over
HTTPS, not through a benchmark container. All requests returned HTTP 200 at
their exact requested HTTPS URLs; redirects were not accepted.

| Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| qunit-1.20.0.js | 112,454 | `576c7117981fae223d412e94e53a176c124f5e3a4dc321b9d56d58ae680015c0` |
| qunit-1.20.0.css | 5,349 | `98abc5dc3d67eb3a1f50eb861c7f888a9a5b43edaa8f29689c50d1841fb915fb` |

The [publisher's version index](https://releases.jquery.com/qunit/) lists both
exact files. Its JavaScript SRI is
`sha256-V2xxF5gfriI9QS6U5ToXbBJPXjpNwyG51W1YrmgAFcA=`, which matches the acquired
script. The index does not publish a CSS SRI; its recorded CSS hash is computed,
not misrepresented as publisher-authenticated metadata.

The upstream 1.20.0 tag resolves to commit
`e943ac9e80d7d46d929fea6ea3135473335650a3`. Both CDN files match the corresponding
`qunit/qunit.js` and `qunit/qunit.css` files from that immutable commit byte for
byte. This is HTTPS provenance, a publisher script integrity check and an
upstream-byte comparison—not a release-signature audit or independent proof
against compromise of both publishing channels. The CSS contains no `url(...)`
references; we did not acquire any additional asset or upgrade a framework.

Raw files, publisher-index HTML, tag response and acquisition metadata are in
`../output/deepswe-survey/testem-qunit-audit-2026-10-09/`. The
[committed manifest](../experiments/deepswe/testem_qunit_assets_verified_2026_10_09.json)
pins the bytes, exact HTTPS sources, upstream commit and verification limits.
The verifier refuses to overwrite an existing capture directory.

## Proposed diagnostic condition

Use a **separate image derived from the exact verified Firefox image**, adding
only the two rehashed assets and a small allowlisted HTTP server. Keep the
original files, copyright headers and tests intact. No dependency installation
or network access is needed during the future build.

Inside the test container, bind the service only to `127.0.0.1:80`, and add the
per-container resolver entry `code.jquery.com:127.0.0.1`. Keep
`--network=none`: this substitutes local delivery for the CDN and grants no
external network access. Do not publish a host port or create a shared network.

The unchanged template's protocol-relative URLs resolve to HTTP because the
real Testem page uses HTTP. Thus the initial design needs no TLS certificate,
trust-store edit or browser security bypass. If Firefox instead upgrades a
request to HTTPS, record that failure and assess it; do not silently disable a
browser security feature or fake a successful response.

Serve only the exact two paths for Host `code.jquery.com` (optionally `:80`),
with real JS/CSS MIME types and the pinned bytes. Unknown hosts, paths and
unsupported methods must fail closed. No directory listing, upstream proxy,
wildcard content, dynamic result generation or missing-favicon replacement.
Log actual requests and response hashes. Verify asset hashes again before
startup and return a harness error if the service cannot start or preflight
fails; do not let a startup failure look like a test outcome.

Use only the verified HOME-only setup under /tmp. Preserve browser arguments,
the original template, repository code and assertions. Retain the runner's
existing command/report handling, public timeouts and every Docker protection:
read-only root, all capabilities dropped, no-new-privileges, 8 GiB memory
without extra swap, two CPUs, 2,048 PIDs and 4 GiB /tmp. The service shares those
limits with the test; it receives no extra resource allowance. No host mount
or credential is needed. Supervise and clean up only the owned service process.

This must be labelled **modified environment: offline public-asset delivery**.
It is not the original image or live-CDN availability. Keep its artifacts apart
from canonical survey results. First run only the same existing failing public
test; a passing result must come from its real assertions, not from canned test
results or a patched reporter. Other CDN-dependent frameworks are outside this
two-asset condition and must not be supplied implicitly.

## Checked prerequisites and limits

A short read-only container check used the current exact Firefox image and all
normal protections, plus the proposed per-container hostname mapping. Python's
HTTP-server module is already available. code.jquery.com resolved only to
127.0.0.1 in the IPv4 check. The image user is UID 0, as in previous Testem runs;
the existing `ip_unprivileged_port_start` value is 0, so port 80 does not require
adding a binding capability. We did not change that sysctl or bind any port.
This checks prerequisites, not actual delivery or service readiness.

No shared runner, canonical configuration or existing image was modified.
No held-out benchmark tests or solutions were read for this assessment; only previously
identified public source and upstream public framework files were used.
Canonical readiness remains 100/113. A successful future diagnostic would not
by itself justify relabelling the original-image survey.

Next, build the separate pinned-asset image and verify its two HTTP responses
offline under the same protections. Only after that preflight should the same
unchanged public test be requested. Neither step has started.
