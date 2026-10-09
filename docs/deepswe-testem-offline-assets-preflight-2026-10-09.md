# Testem: separate offline asset image and HTTP preflight

The separate image built successfully, and **all nine native HTTP checks
passed offline under the original Docker protections**. Both QUnit files were
served with their verified bytes and MIME types. No browser or benchmark test
was run; this is delivery preflight, not a passing Testem baseline.

Tag: `agentless-ml/testem-offline-qunit:2026-10-09`.

```
sha256:96b08a03e607416b109f7d86186d1cdfe92755483eada98693e67ff5f2feba00
```

The parent is the exact verified Firefox image
`sha256:290cd40e1e05814859e3a0430b7bcbea77d92b8fcdd5161fd6ef1c1fc14e969d`.
The builder checked the local parent tag against that ID, rehashed the two
captured assets against the committed manifest, and staged only those files,
the allowlisted service and its Dockerfile. Build steps used `--network=none`
and `--pull=false`. No packages were installed or repository source changed.
The image build verified the hardcoded asset hashes again and made the added
directory non-writable. The builder refuses to overwrite an existing image tag.

## Real HTTP checks

The image's Python server bound only to `127.0.0.1:80`. A per-container entry
mapped code.jquery.com to 127.0.0.1; no host port was published or external
network provided. Requests used that hostname, not a bypassed handler function.

- GET for JavaScript returned 112,454 bytes with SHA-256
  `576c7117981fae223d412e94e53a176c124f5e3a4dc321b9d56d58ae680015c0`.
- GET for CSS returned 5,349 bytes with SHA-256
  `98abc5dc3d67eb3a1f50eb861c7f888a9a5b43edaa8f29689c50d1841fb915fb`.
- Both HEAD requests returned zero body bytes and the correct content length.
- Missing path, favicon, wrong Host and extra query string returned 404.
- POST to a known path returned 501, not a fabricated success.

The service checked both pinned files before listening. Allowed responses
logged the actual path, hash, asset size and bytes sent. It has no proxy,
directory listing, wildcard asset response or test-result generation. The
preflight terminated its owned service process; the host removed its owned
container. No service is left running.

## Protections and limitations

Docker inspection confirmed network=none, read-only root, all capabilities
dropped, no-new-privileges, no privileged mode, 8 GiB memory with no extra swap,
two CPUs, 2,048 PIDs and the same 4 GiB executable/nosuid/nodev /tmp. No sysctl,
capability, certificate trust or Firefox setting was changed. The container
exited zero without OOM. The service shared the container's limits.

The preflight prepared the existing HOME-only path under /tmp, but did not
launch Firefox. It does not establish that Firefox will fetch these URLs or
that the public test passes. No TLS listener was introduced; any unexpected
browser HTTPS upgrade must be investigated separately without disabling
security checks. The original template, tests and public timeouts are unchanged.

This is explicitly **modified environment: offline public-asset delivery**,
not the original benchmark image or live-CDN connectivity. No canonical survey
record was updated; readiness stays 100/113. No held-out tests or solutions
were read. The original Firefox image and earlier diagnostic records remain.

Raw build/preflight records are under
`../output/deepswe-survey/testem-offline-qunit/`: `build.json`, build logs,
`preflight.json`, `preflight.stdout.log` and `preflight.stderr.log`. The
[committed record](../experiments/deepswe/testem_qunit_delivery_preflight_2026_10_09.json)
keeps the exact image IDs, actual HTTP checks and inspected protections.

The subsequent [single unchanged public test](deepswe-testem-offline-public-test-2026-10-09.md)
passed with exit code 0. Its browser fixture reported two passes and one declared
skip; the original reporter returned true. No full-suite retry has started.
