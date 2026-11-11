# DeepSWE pilot closing batch

The four tasks were the next unused entries in the existing ranking. Kysely
and Mobly ran in parallel, followed by the two Obsidian Linter tasks. Both
batches used Sol xhigh, one edit localization, four repair samples per task,
up to ten files, and retained declarations. Docker validation and scoring
shared one slot within each batch.

| Task | Outcome | Issue checks | Regression checks | Provider tokens |
| --- | --- | ---: | ---: | ---: |
| kysely-window-grouping-helpers | No prediction | — | — | 253,033 |
| mobly-grouped-test-barriers | Resolved | 79/79 | 808/808 | 124,520 |
| obsidian-linter-link-format-conversion | Unresolved | 0/60 | 1131/1131 | 172,335 |
| obsidian-linter-auto-table-of-contents | Unresolved | 0/41 | 582/1131 | 161,736 |

Mobly was the sole full pass. Kysely produced four repair responses, but
three searched outside authorized edit ranges and one targeted a file outside
the selection. The table-of-contents patch imported a module that the verifier
could not find. The selected link-conversion patch only changed translations.
Three other candidates created the requested rule file. Their held-out scores
are unknown.

The four tasks used 711,624 provider-reported tokens. Across the development
pilot, 5 of 20 distinct tasks launched earned a full verifier pass. The five
solves were Pebble, Etree, Obsidian Linter's scoped ignore markers, SuperJSON,
and Mobly. The denominator counts repeat attempts once per task and includes
runs that stopped before scoring, including Meriyah's pre-inference budget
stop. The pilot spans different workflow revisions and settings. The reported
fraction describes these attempts and does not estimate performance across
the entire benchmark or compare Agentless-ML with Grinta.

[Run records, candidate evidence, and provenance](final_four/results.json).
