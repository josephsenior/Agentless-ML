"""Live stage requests obey the existing controller, with no feedback repair loop."""

import json
from pathlib import Path

import pytest
from test_fixed_workflow import FakeRunner, controller, responses
from test_fixed_workflow import source as source_fixture

source = source_fixture


def test_fixed_stages_request_responses_then_validate_and_export(tmp_path, source):
    recorded = responses()

    class Provider:
        def __init__(self):
            self.prompts = []

        def complete(self, prompt):
            self.prompts.append(prompt)
            text = [
                recorded.file_localization,
                recorded.symbol_localization,
                "```\ncalculator.py\nline: 2\n```",
                recorded.repairs[2],
            ][len(self.prompts) - 1]
            return {"text": text, "usage": {"input_tokens": 10, "output_tokens": 5}}

    provider = Provider()
    result = controller(tmp_path, source, FakeRunner()).run_live(provider)
    assert result.run.model_calls == 4
    assert result.run.input_tokens == 40 and result.run.output_tokens == 20
    assert len(provider.prompts) == 4
    assert "return a + b" in result.prediction.model_patch
    assert result.run.condition == "agentless-ml-live"
    saved = json.loads((Path(result.artifact_directory) / "responses.json").read_text())
    assert saved["edit_samples"][0]["repairs"] == [recorded.repairs[2]]


def test_failed_provider_does_not_reach_validation_or_retry(tmp_path, source):
    class Provider:
        calls = 0

        def complete(self, prompt):
            self.calls += 1
            raise RuntimeError("connection failed")

    provider = Provider()
    with pytest.raises(RuntimeError, match="connection failed"):
        controller(tmp_path, source, FakeRunner()).run_live(provider)
    assert provider.calls == 1
