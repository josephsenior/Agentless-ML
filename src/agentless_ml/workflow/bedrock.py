"""Text-only Responses requests billed through Amazon Bedrock."""

import json
import os
import re
import urllib.error
import urllib.request


class BedrockResponseError(RuntimeError):
    """A Bedrock request failed or returned an unusable response."""


class BedrockResponses:
    provider_name = "bedrock"

    def __init__(self, *, model="gpt-6.2-sol", reasoning="xhigh", region="eu-west-3"):
        if not re.fullmatch(r"[a-z]{2}(?:-[a-z]+)+-\d+", region):
            raise ValueError("Expected an AWS region such as eu-west-3")
        if not re.fullmatch(r"gpt-[a-z0-9.-]+", model):
            raise ValueError("Expected an OpenAI model name such as gpt-6.2-sol")
        self._api_key = os.environ.get("AWS_BEARER_TOKEN_BEDROCK", "").strip()
        if not self._api_key:
            raise ValueError("Set AWS_BEARER_TOKEN_BEDROCK to your Bedrock API key")
        self.region = region
        self.model = model
        self.reasoning = reasoning
        self.profile = "global.openai." + model

    @property
    def settings(self):
        return {
            "provider": self.provider_name,
            "region": self.region,
            "model": self.model,
            "inference_profile": self.profile,
            "reasoning": self.reasoning,
        }

    def complete(self, prompt, *, remaining_seconds=None):
        if remaining_seconds is not None and remaining_seconds <= 0:
            raise BedrockResponseError("No time remains for a Bedrock request")
        # Allow long reasoning calls while capping the socket timeout by the
        # time the controller reports as remaining.
        timeout = min(1200, remaining_seconds) if remaining_seconds is not None else 1200
        request = urllib.request.Request(
            f"https://bedrock-runtime.{self.region}.amazonaws.com/openai/v1/responses",
            data=json.dumps({
                "model": self.profile,
                "input": [{"role": "user", "content": prompt}],
                "reasoning": {"effort": self.reasoning},
                "store": False,
            }).encode("utf-8"),
            headers={"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as reply:
                response = json.load(reply)
        except urllib.error.HTTPError as exc:
            raise BedrockResponseError(f"Bedrock request failed with HTTP {exc.code}") from None
        except (OSError, ValueError) as exc:
            raise BedrockResponseError(f"Bedrock response failed ({type(exc).__name__})") from None
        if response.get("status") != "completed":
            raise BedrockResponseError("Bedrock did not return a completed response")
        reported_model = response.get("model")
        if reported_model not in {self.model, "openai." + self.model, self.profile}:
            raise BedrockResponseError("Bedrock response model differs from the requested model")
        text = "".join(
            part["text"]
            for item in response.get("output", []) if item["type"] == "message"
            for part in item["content"] if part["type"] == "output_text"
        )
        # An empty message is valid for regression selection. The controller
        # validates the text and usage according to the stage.
        return {"text": text, "usage": response.get("usage"), "model": self.model,
                "reported_model": reported_model}
