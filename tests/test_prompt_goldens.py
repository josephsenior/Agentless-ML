"""Pin every model-visible prompt each language renders for fixed inputs."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from capture_prompt_fixtures import ROOT, load_cases, render  # noqa: E402

CASES = load_cases()


@pytest.mark.parametrize("language", CASES["languages"])
def test_prompts_unchanged(language):
    rendered = render(language, CASES["languages"][language], CASES["problem_statement"])
    for stage, prompt in rendered.items():
        expected = (ROOT / language / f"{stage}.txt").read_text(encoding="utf-8")
        assert prompt == expected, (
            f"{language} {stage} prompt changed; this is model-visible. Review the "
            "difference, then re-capture with: python tools/capture_prompt_fixtures.py"
        )
