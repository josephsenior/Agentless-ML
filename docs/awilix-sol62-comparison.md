# Awilix with GPT-6.2 Sol and GPT-6.1 Sol

GPT-6.2 Sol at xhigh resolved the Awilix async initialization task. The selected
patch passed the child-scope initialization check that GPT-6.1 Sol had missed.

| Measure | GPT-6.1 Sol xhigh | GPT-6.2 Sol xhigh |
| --- | ---: | ---: |
| Issue checks | 23/24 | 24/24 |
| Verifier regression checks | 162/162 | 162/162 |
| Candidates passing all 158 public checks | 3/4 | 3/4 |
| Processed tokens | 125,520 | 100,483 |
| Controller runtime before scoring | 12m 55s | 14m 15s |

The runs used the same pinned base, image, declaration index, sampling settings,
and limits. The repeat kept Windows awake through scoring. Both models selected
the same four files. Prompts matched through symbol localization, and the later
prompts differed because the models selected different source locations.

The GPT-6.2 patch checks whether a singleton is registered on the current scope
before adding it to that scope's initialization schedule. This keeps inherited
parent singletons out of the schedule. Three candidates passed the public suite,
and the existing tie-break selected the first. The verifier scored that patch.

GPT-6.2 used 19.9% fewer processed tokens and took about 80 seconds longer on this
repeat. The comparison covers one scored attempt per model on Awilix.

[GPT-6.2 record](../experiments/pilots/deepswe_small_v2/awilix_declaration_index_sol62_2026-11-18/result.json) ·
[Selected patch](../experiments/pilots/deepswe_small_v2/awilix_declaration_index_sol62_2026-11-18/selected.patch) ·
[GPT-6.1 run](awilix-declaration-index-run.md)
