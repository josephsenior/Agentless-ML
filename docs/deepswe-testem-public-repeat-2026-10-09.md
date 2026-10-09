# Testem: uninterrupted full public repeat

The same full schedule completed in **370.937 seconds**, within the unchanged
1,800-second cap. It returned exit code 9 and a usable failing report, rather
than a timeout or harness error. No host interruption was observed this time.

The normalized result is **489 passed, three skipped and eight failed** across
500 distinct test IDs. The raw XML contains 504 testcase nodes: 492 passing,
three skipped and nine failing nodes. Three IDs repeat: a Config test appears
three times, a Launcher test twice, and one failing afterEach hook twice. The
existing report parser keeps the worst outcome for each ID. No result was
filtered or changed to make the run pass.

The XML suite header says 502 tests, nine errors and one skipped; those totals
do not match its actual child nodes. We retain both and use the testcase nodes,
not that header, for normalization. Mocha's exit code agrees with the nine raw
failure nodes, including the duplicated hook failure.

## What stayed unchanged

The image was
`sha256:290cd40e1e05814859e3a0430b7bcbea77d92b8fcdd5161fd6ef1c1fc14e969d`.
The sealed candidate revision was
`158f61ea91c9613d2011c41ee9be40ada1d7a307`. Both public globs and the existing
Mocha/xUnit command are identical to the interrupted attempt. No test source,
assertion, browser flag, public timeout, dependency or environment workaround
was changed for this repeat.

The same runner retained offline networking, read-only root, dropped
capabilities, no-new-privileges, 8 GiB memory without extra swap, two CPUs,
2,048 PIDs and 4 GiB temporary storage. Read-only probes found no cgroup OOM
events, mostly empty temporary storage and a sampled peak-memory counter of
214,937,600 bytes (205 MiB). That counter was sampled before completion, not
claimed as the final peak. The Windows keep-awake request was scoped to this
attempt and released afterwards. The owned container was removed.

## Remaining failures

Five CI assertions concern browser results: missing Firefox launcher results,
unexpected exit status, incorrect todo totals and the two-browser scenario.
The interactive page-reload test hit its public 90-second timeout. The report
file test hit its public 30-second timeout, and a report-file afterEach hook
failed twice with mismatched temporary report paths. These are observations,
not proof of one shared root cause. Hook failures may be fallout from earlier
asynchronous failures; that has not been established.

Firefox processes existed during the run, but that alone does not prove they
loaded the test pages or connected to Testem. The earlier standalone screenshot
check used different invocation/profile/home handling. It therefore does not
resolve these full-suite failures. No protection was relaxed to investigate
them, and no further test attempt was started.

Raw evidence is retained under
`../output/deepswe-survey/testem-firefox/logs/agentless-ml-b478d9a3df54423aa2c3e367d8ad2899/`:
`execution.json`, `public-schedule.json`, `report.xml`, `stdout.log` and
`stderr.log`. The [compact record](../experiments/deepswe/testem_public_repeat_2026_10_09.json)
preserves both raw and normalized counts and the exact command.

## Next step

The subsequent [targeted connection diagnostic](deepswe-testem-firefox-connection-2026-10-09.md)
observed no HTTP requests from Firefox in one unchanged failing public test.
Synthetic controls connected only with writable home/cache paths, for either
argument order. This identifies a concrete environment difference, not a fix
or proof that all eight failures share one cause. No full repeat followed.

This is a **completed but failing baseline in the separate Firefox condition**,
not a passing baseline or an update to the original-image survey. Canonical
readiness remains 100/113. No held-out tests or solutions were read. The earlier
interrupted record is preserved unchanged; KGateway, Numba and Pwntools remain
parked.
