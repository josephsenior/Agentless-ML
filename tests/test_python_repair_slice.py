import json
from pathlib import Path

from agentless_ml.repair import (
    apply_search_replace_edits,
    build_patch_candidate,
    build_repair_prompt,
    build_unified_diff,
    parse_search_replace_edits,
    select_final_prediction,
)


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "python"


def test_recorded_response_reaches_final_prediction_from_real_python_fixture() -> None:
    repository = json.loads(
        (FIXTURE_DIR / "requests-2317.agentless-v1.5.0.json").read_text(
            encoding="utf-8"
        )
    )
    locations = json.loads(
        (FIXTURE_DIR / "requests-2317.locations.agentless-v1.5.0.json").read_text(
            encoding="utf-8"
        )
    )
    path = repository["capture"]["selected_file"]
    source = repository["selected_source"]
    prompt = build_repair_prompt(
        repository["capture"]["problem_statement"], locations["selected_context"]
    )
    assert path in prompt

    recorded_response = f"""```python
### {path}
{'<' * 7} SEARCH
        method = builtin_str(method)
{'=' * 7}
        method = to_native_string(method)
{'>' * 7} REPLACE
```"""
    edits = parse_search_replace_edits(recorded_response)
    applied = apply_search_replace_edits(
        {path: source},
        edits,
        allowed_intervals={
            path: [
                tuple(span) for span in locations["selected_intervals"][path]
            ]
        },
    )
    patch = build_unified_diff(applied.original_sources, applied.updated_sources)
    candidate = build_patch_candidate(
        candidate_id="loc-0-repair-0",
        raw_response=recorded_response,
        diff=patch,
        localization_rank=0,
        sample_index=0,
    )
    prediction = select_final_prediction(
        instance_id=repository["capture"]["instance_id"],
        model_name="recorded/test-model",
        candidates=[candidate],
    )

    assert prediction.selected_candidate_id == "loc-0-repair-0"
    assert "-        method = builtin_str(method)" in prediction.model_patch
    assert "+        method = to_native_string(method)" in prediction.model_patch
