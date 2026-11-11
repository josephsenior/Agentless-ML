# DynamoDB Toolbox conditional attribute requirements

On 11 November 2026, `dynamodb-toolbox-conditional-attribute-requirements` was
the next fresh task in the existing ranking after ts-pattern. The public
baseline passed all 1,267 tests. The attempt used Sol xhigh and four concurrent
repair samples under the existing fixed workflow.

All eight responses arrived. All four repair responses described integration
points in prose and contained zero SEARCH/REPLACE blocks. The controller had
no candidate to validate or export, so the attempt ended before final scoring.

File localization used all five slots on schema properties, item and map
parsing, and the two update parameter builders. One response explicitly
requested builder, schema-checking, DTO and export definitions before providing
a patch. Those definitions did not have source sections in the repair prompt.

The provider reported 79,108 tokens. The launcher leaves its `model_calls`
field at zero when the workflow stops before export. The eight saved responses
and `completed_model_responses` field record the actual calls.

[Run evidence](dynamodb_toolbox_xhigh_2026-11-11/summary.json).
