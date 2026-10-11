"""Opt-in full Docker controller slice; never execute authored Rust on the host."""

import os
from pathlib import Path
import runpy

import pytest


@pytest.mark.skipif(os.environ.get("AGENTLESS_RUST_REPRODUCTION_DOCKER_TESTS") != "1",
                    reason="opt-in pinned Rust controller diagnostic")
def test_recorded_rust_controller_slice(tmp_path):
    tool = runpy.run_path(str(Path(__file__).resolve().parents[1] / "tools/run_recorded_rust_slice.py"))
    summary = tool["run_slice"](tmp_path / "rust-controller")
    assert summary["selected_candidate_id"] == "repair-2"
    assert summary["candidate_outcomes"] == [["pass", "fail"], ["pass", "pass"]]
