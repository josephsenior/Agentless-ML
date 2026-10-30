"""Exercise the real subscription worker with an offline SDK stream."""

import io
import json
import sys
from types import SimpleNamespace as NS

import pytest

from agentless_ml.workflow.subscription import WORKER


@pytest.mark.parametrize("remaining,process_timeout,http_timeout", [
    (600, 600, 120), (30, 30, 30), (None, 180, 120),
])
def test_worker_deadline_uses_remaining_attempt_time(
    tmp_path, monkeypatch, remaining, process_timeout, http_timeout
):
    import os
    import subprocess

    from agentless_ml.workflow.subscription import SubscriptionResponses

    python = tmp_path / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    python.parent.mkdir(parents=True)
    python.touch()

    def run(argv, **kwargs):
        assert kwargs["timeout"] == process_timeout
        assert json.loads(kwargs["input"])["timeout"] == http_timeout
        return subprocess.CompletedProcess(argv, 0, json.dumps({"text": "patch"}), "")

    monkeypatch.setattr(subprocess, "run", run)
    result = SubscriptionResponses(tmp_path).complete("repair", remaining_seconds=remaining)
    assert result["text"] == "patch"


def run_worker(monkeypatch, capsys, events):
    class Stream:
        def __enter__(self):
            return iter(events)

        def __exit__(self, *args):
            return False

    client = NS(responses=NS(create=lambda **kwargs: Stream()))
    monkeypatch.setitem(sys.modules, "openai", NS(OpenAI=lambda **kwargs: client))
    monkeypatch.setitem(
        sys.modules, "backend.inference.clients.chatgpt_plan_auth",
        NS(access_token=lambda profile: "offline-token"),
    )
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({
        "profile": "default", "timeout": 120, "model": "gpt-6.1-sol",
        "reasoning": "medium", "prompt": "Locate files.",
    })))
    exec(WORKER, {})
    return json.loads(capsys.readouterr().out)


def completed(output=()):
    return NS(type="response.completed", response=NS(
        output=output, model="gpt-6.1-sol",
        usage=NS(model_dump=lambda: {"input_tokens": 10, "output_tokens": 5}),
    ))


@pytest.mark.parametrize("source", ["item", "delta", "text_done", "completed"])
def test_worker_keeps_streamed_text_when_final_event_omits_it(monkeypatch, capsys, source):
    item = NS(type="message", content=[NS(type="output_text", text="a.py")])
    events = {
        "item": [NS(type="response.output_item.done", output_index=0, item=item), completed()],
        "delta": [NS(type="response.output_text.delta", output_index=0, content_index=0,
                     delta="a.py"), completed()],
        "text_done": [NS(type="response.output_text.delta", output_index=0, content_index=0,
                         delta="a."), NS(type="response.output_text.done", output_index=0,
                                        content_index=0, text="a.py"), completed()],
        "completed": [completed([item])],
    }[source]
    result = run_worker(monkeypatch, capsys, events)
    assert result["text"] == "a.py"
    assert result["usage"] == {"input_tokens": 10, "output_tokens": 5}


def test_worker_still_allows_genuinely_empty_completed_answer(monkeypatch, capsys):
    assert run_worker(monkeypatch, capsys, [completed()])["text"] == ""


@pytest.mark.parametrize("terminal", [None, "response.failed", "response.incomplete", "error"])
def test_worker_never_accepts_partial_text_without_completion(monkeypatch, capsys, terminal):
    events = [NS(type="response.output_text.delta", output_index=0, content_index=0,
                 delta="a.py")]
    if terminal:
        events.append(NS(type=terminal))
    with pytest.raises(RuntimeError):
        run_worker(monkeypatch, capsys, events)
