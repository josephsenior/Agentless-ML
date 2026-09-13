"""Capture the model-visible prompts each language renders for fixed inputs.

    python tools/capture_prompt_fixtures.py

Overwrites tests/fixtures/prompts/<language>/*.txt. Prompts are what the model
reads, so run this only before a deliberate prompt change (to record the
baseline) or after reviewing one.
"""

from __future__ import annotations

import json
from pathlib import Path

from agentless_ml.adapters.languages import get_language_adapter
from agentless_ml.localization.context import (
    render_file_localization_prompt,
    render_project_tree,
    render_symbol_localization_prompt,
)
from agentless_ml.repair import build_repair_prompt

ROOT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "prompts"


def render(language: str, case: dict, problem: str) -> dict[str, str]:
    adapter = get_language_adapter(language)
    tree = render_project_tree(case["repository_paths"], adapter=adapter)
    return {
        "file_localization": render_file_localization_prompt(
            problem, tree, extension=adapter.extension
        ),
        "symbol_localization": render_symbol_localization_prompt(
            problem, case["files"], adapter=adapter
        ),
        "repair": build_repair_prompt(problem, case["repair_context"], language=language),
    }


def load_cases() -> dict:
    return json.loads((ROOT / "cases.json").read_text(encoding="utf-8"))


def main() -> None:
    cases = load_cases()
    for language, case in cases["languages"].items():
        for stage, prompt in render(language, case, cases["problem_statement"]).items():
            target = ROOT / language / f"{stage}.txt"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(prompt, encoding="utf-8", newline="\n")
    print(f"captured prompts for {len(cases['languages'])} languages into {ROOT}")


if __name__ == "__main__":
    main()
