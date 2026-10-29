"""The subscription response client accepts only completed streams."""

import io
import json

import pytest

from agentless_ml.workflow.chatgpt_response import ChatGPTResponseError, request_response


def test_completed_response_and_usage(monkeypatch):
    def open_request(request, timeout):
        body = json.loads(request.data)
        assert body["store"] is False and body["stream"] is True
        assert "tools" not in body
        assert body["input"][0]["content"] == "locate files"
        assert request.full_url == "https://api.openai.com/v1/responses"
        return io.BytesIO(
            b'data: {"type":"response.output_text.delta","delta":"hello"}\n\n'
            b'data: {"type":"response.completed","response":{"model":"model-a","usage":{"input_tokens":2}}}\n\n'
        )

    monkeypatch.setattr("urllib.request.urlopen", open_request)
    result = request_response("locate files", access_token="test", model="model-a")
    assert result == {"text": "hello", "usage": {"input_tokens": 2}, "model": "model-a"}


def test_interrupted_stream_is_not_accepted(monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: io.BytesIO(
        b'data: {"type":"response.output_text.delta","delta":"partial"}\n\n'
    ))
    with pytest.raises(ChatGPTResponseError, match="before completion"):
        request_response("prompt", access_token="test", model="model-a")
