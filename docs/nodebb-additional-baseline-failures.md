# Two additional NodeBB failures: investigation

Both failures exposed by the no-bail diagnostic can be explained from the
pinned base and original image. Neither calls for another dependency workaround.
This investigation changed no repository code, tests, fixtures or runner
settings and did not repeat the suite.

## Category actor summary

The public fixture at `test/activitypub/actors.js:139–149` creates a category
with a random description and no `federatedDescription`. The assertion at
line 169 expects the returned actor's `summary` to equal that description.

The category endpoint at `src/controllers/activitypub/actors.js:193` returns
`activitypub.mocks.actors.category(cid)`. In `src/activitypub/mocks.js:414–443`,
that function starts with `descriptionParsed`, translates the default
federation description and unconditionally appends:

```javascript
summary += `<hr /><p dir="auto">${federatedDescription || fallback}</p>\n`;
```

The English fallback in
`public/language/en-GB/admin/manage/categories.json:15` is exactly the explanatory
text in the saved failure. Thus the observed extra HTML follows the pinned
implementation directly. The code and test disagree about the summary
contract; the investigation does not determine which upstream behavior should
be corrected. Do not alter either as a setup fix.

## Azerbaijani file inventory

`test/i18n.js:34–36` walks every file in `public/language/en-GB` and builds
`sourceFiles` without excluding the documentation marker. The test at
lines 116–118 then requires every source entry in each language directory.
The file walker at `src/file.js:149–153` has no extension filter.

The marker `_DO_NOT_EDIT_FILES_HERE.md` is committed in `en-GB` as Git blob
`1faf87ad651dee793f4423e92cca0964fdf63e92`, but there is no corresponding path
in `az` at the pinned HEAD. The original image has the same presence/absence.
Its content is documentation directing contributors to the translation README,
not a missing translation JSON file.

Other checks in this same test file explicitly ignore the marker when loading
JSON or validating translation keys, but the cross-language file-inventory
check does not. This explains the failure without a download, locale package,
Docker permission or generated-output problem. Do not add/delete marker files
to make the assertion green.

The i18n suite also has a public CI-context skip for pull requests or specified
non-develop refs. Setting those variables solely to skip the failure would
remove coverage, not fix infrastructure. No such setting was introduced.

## Provenance and limits

All inspected candidate files have no diff from the sealed base commit
`61d17c95e573f91ab5c65d25218451e9afd07d77`. A read-only offline container compared
the relevant public files in the original image with the checkout. Their raw
hashes differ because the Windows checkout uses CRLF; after CRLF-to-LF
normalization, all four checked files match byte-for-byte. The absent `az`
marker was verified separately. See the
[investigation evidence](../experiments/swe_bench_pro/v2_js_nodebb_upload_path/additional-failure-investigation-2026-10-14.json).

These are source-based diagnoses corroborated by the existing executed report,
not fresh isolated assertion replays. No new test or candidate validation ran.
The [no-bail inventory](nodebb-no-bail-diagnostic.md) remains 8,089 passes and
three retained failures, with complete coverage for that labelled condition.

Next: review whether to register that explicit diagnostic inventory with its
three existing failures, rather than attempting to make the base repository
all-green. Registration must retain the non-default no-bail and live-network
labels; it cannot silently become the repository-default baseline, an official
score or an offline candidate-selection condition. No registration was made
by this investigation.
