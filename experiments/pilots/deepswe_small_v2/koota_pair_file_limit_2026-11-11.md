# Five versus ten files on Koota pair tracking

This pilot used the next unused task in the existing ranking on 11 November
2026. Both runs used Sol xhigh, four concurrent repairs, one edit localization,
the same token and time limits, and declaration retention. File localization
could return up to five files in the first run and ten in the second.

| File limit | Files selected | Public baseline | Exported patch | Provider tokens | Workflow time after baseline |
| --- | ---: | ---: | --- | ---: | ---: |
| 5 | 5 | 172/172 | None | 65,529 | 11.5 minutes |
| 10 | 10 | 172/172 | None | 105,066 | 18.2 minutes |

Each run completed eight model calls. Every repair prompt requested
SEARCH/REPLACE blocks, and the eight repair responses contained zero such
blocks. The parser reported a missing edit for each response, before patch
application or candidate tests. Neither run has a verifier score. The launcher
reports the completed response count separately from its zero-initialized
model-call field on runs that end before export.

The ten-file run included the tracking factories and entity and query types.
The repair responses still requested editable excerpts for relation mutations
and the implementation of `entity.changed`. Some code required for the task
remained outside the selected files or the fine edit excerpts. The read-only
declarations did not make those additional regions editable.

This pair establishes a difference in source coverage, token use and elapsed
time on one task. Both runs stopped before producing a patch, and one task
cannot establish an effect on the overall resolve rate.

[Run evidence](koota_pair_file_limit_2026-11-11.json).
