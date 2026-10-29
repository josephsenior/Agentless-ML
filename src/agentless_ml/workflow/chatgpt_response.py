"""A single text response using an independently authorized ChatGPT-plan token.

The caller owns the fixed workflow and supplies each prompt. Credentials must be
obtained through the documented Sign in with ChatGPT flow, not a Codex auth file.
"""

import json
import urllib.error
import urllib.request


class ChatGPTResponseError(RuntimeError):
    """A model response did not complete successfully."""


def request_response(prompt, *, access_token, model, reasoning="medium", timeout=120):
    """Return completed text and usage; never execute tools or retain a session."""
    if not prompt.strip() or not access_token or not model:
        raise ValueError("prompt, authorized access token, and model are required")
    payload = {
        "model": model,
        "input": [{"role": "user", "content": prompt}],
        "reasoning": {"effort": reasoning},
        "store": False,
        "stream": True,
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode(),
        headers={"Authorization": "Bearer " + access_token, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as stream:
            chunks = []
            for raw in stream:
                line = raw.decode("utf-8").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                event = json.loads(data)
                kind = event.get("type")
                if kind == "response.output_text.delta":
                    chunks.append(event.get("delta", ""))
                elif kind == "response.completed":
                    response = event.get("response", {})
                    text = "".join(chunks)
                    if not text.strip():
                        raise ChatGPTResponseError("model returned an empty response")
                    return {"text": text, "usage": response.get("usage"), "model": response.get("model", model)}
                elif kind in {"response.failed", "response.incomplete", "error"}:
                    raise ChatGPTResponseError("model request failed or was incomplete")
    except (urllib.error.URLError, TimeoutError, UnicodeError, json.JSONDecodeError) as exc:
        raise ChatGPTResponseError(f"model connection failed: {type(exc).__name__}") from exc
    raise ChatGPTResponseError("model stream ended before completion")
