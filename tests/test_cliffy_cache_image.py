import hashlib
import json
from pathlib import Path


def test_deno_cache_key_and_footer_match_observed_format(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "tools"))
    from build_cliffy_cache_image import cache_entry
    url = "https://jsr.io/@std/path/1.1.5/posix/glob_to_regexp.ts"
    key, data = cache_entry(url, b"source\n")
    assert key == "90f1df71ffa1ca7c3a138b7f72d4969e36aed3ae5f55190b11c58cf87eb6dfb6"
    body, footer = data.rsplit(b"\n// denoCacheMetadata=", 1)
    assert body == b"source\n"
    assert json.loads(footer)["url"] == url


def test_graph_check_keeps_native_discovery_without_executing_tests(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "tools"))
    from check_cliffy_offline_graph import graph_command
    from agentless_ml.adapters.benchmarks.deepswe_execution import DENO
    original = DENO.command((), timeout_seconds=1800)
    check = graph_command()
    assert "deno test --no-run --cached-only" in check.argv[2]
    assert check.argv[2].replace(" --no-run", "") == original.argv[2]
    assert check.report is None
    assert check.argv[3:] == original.argv[3:]


def test_cache_staging_rejects_changed_saved_bytes(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "tools"))
    import build_cliffy_cache_image as build
    import pytest
    monkeypatch.setattr(build, "ROOT", tmp_path / "repo")
    path = tmp_path / "output/deepswe-survey/cliffy-public-dependencies-2026-10-09/blob"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"changed")
    item = {"artifact": path.relative_to(tmp_path).as_posix(), "bytes": 7,
            "sha256": hashlib.sha256(b"original").hexdigest()}
    with pytest.raises(ValueError, match="changed"):
        build.checked_blob(item)


def test_full_schedule_is_exactly_the_existing_public_command(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "tools"))
    from check_cliffy_offline_graph import selected_command
    from agentless_ml.adapters.benchmarks.deepswe_execution import DENO
    assert selected_command(True) == DENO.command((), timeout_seconds=1800)
    assert "--no-run" not in selected_command(True).argv[2]
    assert selected_command(True).report == DENO.report
    assert selected_command(False).report is None
