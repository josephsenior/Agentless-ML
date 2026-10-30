"""Live stage requests obey the existing controller, with no feedback repair loop."""

import json
from pathlib import Path

import pytest
from test_fixed_workflow import FakeRunner, controller, responses
from test_fixed_workflow import source as source_fixture

source = source_fixture


def test_live_workflow_reports_content_and_processed_usage_separately(tmp_path, source):
    from agentless_ml.attempt_budget import AttemptBudget

    recorded = responses()

    class Provider:
        calls = 0

        def complete(self, prompt, **kwargs):
            text = [recorded.file_localization, recorded.symbol_localization,
                    "```\ncalculator.py\nline: 2\n```", recorded.repairs[2]][self.calls]
            self.calls += 1
            return {"text": text, "usage": {"input_tokens": 1000000, "output_tokens": 5}}

    budget = AttemptBudget.pilot()
    result = controller(tmp_path, source, FakeRunner()).run_live(Provider(), budget=budget)
    evidence = json.loads((Path(result.artifact_directory) / "budget.json").read_text())
    assert evidence["processed_tokens"] == 4000020
    assert 0 < evidence["used_tokens"] < 1000000
    assert evidence["token_accounting"] == "once_only_context"
    assert "return a + b" in result.prediction.model_patch


def test_live_regression_selection_accepts_empty_answer_and_records_usage(
    tmp_path, source
):
    from test_fixed_workflow import RegressionRunner, regression_controller

    recorded = responses()

    class Provider:
        calls = 0

        def complete(self, prompt):
            text = [
                "",
                recorded.file_localization,
                recorded.symbol_localization,
                "```\ncalculator.py\nline: 2\n```",
                recorded.repairs[2],
            ][self.calls]
            self.calls += 1
            return {"text": text, "usage": {"input_tokens": 10, "output_tokens": 5}}

    from agentless_ml.validation import RegressionTest, PublicTestCommand
    workflow = regression_controller(tmp_path, source, RegressionRunner())
    workflow.regression_tests = (RegressionTest('keep', PublicTestCommand(('keep',))),)
    result = workflow.run_live(Provider())
    assert result.run.model_calls == 5
    first = json.loads(
        (Path(result.artifact_directory) / "model-calls/1/response.json").read_text()
    )
    assert first["text"] == "" and first["usage"]["input_tokens"] == 10


def test_live_token_limit_prevents_another_stage(tmp_path, source):
    from agentless_ml.attempt_budget import AttemptBudget, BudgetExceeded

    recorded = responses()

    class Provider:
        calls = 0

        def complete(self, prompt, **kwargs):
            self.calls += 1
            return {
                "text": recorded.file_localization,
                "usage": {"input_tokens": 10, "output_tokens": 5},
            }

    provider = Provider()
    with pytest.raises(BudgetExceeded):
        controller(tmp_path, source, FakeRunner()).run_live(
            provider, budget=AttemptBudget(tokens=15)
        )
    assert provider.calls == 1
    evidence = json.loads(next((tmp_path / "runs").glob("*/budget.json")).read_text())
    assert evidence["used_tokens"] == 15


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
