# ActivityPub URL assertion: source investigation

> Development record. See [the documentation guide](../README.md) for current status.

The writable-copy full run reached 4,508 passing tests before an ActivityPub
assertion expected an actor URL and received `null`. Read-only inspection of
the pinned base explains that result without a new Docker or network change.

## The mismatch

At `test/activitypub/actors.js:58–59`, the public test requests
`user.getUserField(actorUri, 'url')` and expects the fixture's actor URI.

The pinned implementation follows this path:

1. `src/activitypub/mocks.js:225` puts the actor's `url` in the profile payload.
   `src/activitypub/actors.js` submits that profile under `userRemote:<actorUri>`.
2. `src/user/data.js:99–114` reads remote-user fields and calls `modifyUserData`.
3. At lines 237–242, `modifyUserData` explicitly assigns
   `user.remoteUrl = user.url`, then deletes `user.url`. Its comment says this
   works around template `renderOverride` supplying `url`.
4. At lines 162–164, `getUserField` returns the requested property only if it
   still exists; otherwise it returns `null`.

Consequently, asking this reader for `url` cannot return that field even when
the raw database value was correctly stored. The code and test disagree about
the returned field contract. This establishes a pinned-base mismatch; it does
not establish whether the intended upstream correction belongs in the reader
or in the test. We did not change either.

## Why this is not another dependency/cache problem

The existing report records passes for the two immediately preceding cases:
asserting the actor succeeds, and its remote-user representation exists in the
database. The fixture seeds ActivityPub's in-memory cache with both `id` and
`url`. `CI=true` makes actor assertion use that cache; the cached-response path
in `src/activitypub/index.js:275–288` returns before a network request.

The unconditional field deletion explains the reported `null` without assuming
network failure, missing npm packages or interference from earlier tests. No
new execution was needed for this source diagnosis. An isolated runtime replay
has not been performed, and no raw database URL was newly measured; the finding
is based on the executed report plus the inspected data-reading path.

The inspected files have no diff against the sealed base commit
`61d17c95e573f91ab5c65d25218451e9afd07d77`. Their checksums and the observed
preceding outcomes are in the
[investigation record](../../experiments/swe_bench_pro/v2_js_nodebb_upload_path/activitypub-assertion-investigation-2026-10-14.json).
The [original full-run evidence](../../experiments/swe_bench_pro/v2_js_nodebb_upload_path/writable-full-public-2026-10-14.json)
remains unchanged.

## What to do next

Keep this assertion as a recorded existing baseline failure. Do not patch
candidate source, change the public assertion, omit it or reinterpret it as a
pass to improve readiness. No retry or implementation fix was made during this
investigation.

The repository's `bail:true` prevents collecting the rest of the suite after
this failure. Review a **separately labelled no-bail diagnostic** to inventory
the remaining public cases while retaining every failure. That would change a
runner option, so it must not be described as the unchanged repository-default
schedule or silently registered as an official result. Any eventual regression
selection plan needs a declared complete baseline and matching candidate
conditions; network-enabled diagnostic results remain separate from offline
agent-side selection. NodeBB's current full-baseline readiness stays false.

The subsequent [explicit no-bail diagnostic](nodebb-no-bail-diagnostic.md)
completed all 8,092 cases, preserving this assertion failure and exposing two
additional failures. It provides a complete diagnostic inventory, not a
passing repository-default run.
