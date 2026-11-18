import io
import json
import urllib.error
from unittest.mock import patch

import pytest

from agentless_ml.workflow.bedrock import BedrockResponseError, BedrockResponses


def test_bedrock_loads_only_its_key_from_dotenv(monkeypatch, tmp_path):
    monkeypatch.delenv("AWS_BEARER_TOKEN_BEDROCK", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("# Keys\nUNRELATED=ignore\nAWS_BEARER_TOKEN_BEDROCK=local-key==\n")
    provider = BedrockResponses(env_file=env_file)
    with patch("urllib.request.urlopen", side_effect=OSError) as send:
        with pytest.raises(BedrockResponseError):
            provider.complete("Repair this")
    assert send.call_args.args[0].get_header("Authorization") == "Bearer local-key=="
    monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "env-key")
    with patch("urllib.request.urlopen", side_effect=OSError) as send:
        with pytest.raises(BedrockResponseError):
            BedrockResponses(env_file=env_file).complete("Repair this")
    assert send.call_args.args[0].get_header("Authorization") == "Bearer env-key"


def test_bedrock_profiles_and_returns_empty_regression_response(monkeypatch):
    monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "test-secret")
    provider = BedrockResponses()
    output = {"status": "completed", "model": provider.profile, "output": [],
              "usage": {"input_tokens": 10, "output_tokens": 2}}
    with patch("urllib.request.urlopen", return_value=io.BytesIO(json.dumps(output).encode())) as send:
        result = provider.complete("Select tests", remaining_seconds=20)
    request = send.call_args.args[0]
    assert request.full_url == "https://bedrock-runtime.eu-west-3.amazonaws.com/openai/v1/responses"
    assert request.get_header("Authorization") == "Bearer test-secret"
    payload = json.loads(request.data)
    assert payload["model"] == "global.openai.gpt-6.2-sol"
    assert payload["reasoning"] == {"effort": "xhigh"} and payload["store"] is False
    assert send.call_args.kwargs["timeout"] == 20
    assert "test-secret" not in repr(provider.settings)
    assert result == {"text": "", "usage": output["usage"], "model": "gpt-6.2-sol",
                      "reported_model": "global.openai.gpt-6.2-sol"}


def test_bedrock_preserves_status_without_recording_error_body(monkeypatch):
    monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "test-secret")
    provider = BedrockResponses()
    error = urllib.error.HTTPError("https://example.invalid", 403, "test-secret", None, None)
    with patch("urllib.request.urlopen", side_effect=error):
        with pytest.raises(BedrockResponseError, match="^Bedrock request failed with HTTP 403$"):
            provider.complete("Repair this")
