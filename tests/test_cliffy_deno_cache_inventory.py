import json
from pathlib import Path


def test_inventory_distinguishes_missing_metadata_from_cached_sources(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "tools"))
    from inspect_cliffy_deno_cache import inventory

    (tmp_path / "source").write_text('source\n' + json.dumps({
        "url": "https://jsr.io/@std/io/0.225.3/types.ts",
    }, separators=(",", ":")))
    (tmp_path / "metadata").write_text('{}\n' + json.dumps({
        "url": "https://jsr.io/@std/assert/meta.json",
    }, separators=(",", ":")))
    config = {"imports": {"@std/io": "jsr:@std/io@~0.225.3",
                          "@std/assert": "jsr:@std/assert@^1.0.18",
                          "@cliffy/prompt": "jsr:@cliffy/prompt@1.0.0",
                          "sinon": "npm:sinon@^21.0.1"}}
    result = inventory(config, tmp_path)
    assert result["missing_package_metadata"] == ["@std/io"]
    assert result["requested_jsr_packages"]["@std/io"]["files"] == 1
    assert result["requested_jsr_packages"]["@std/assert"]["package_metadata"]
    assert "@cliffy/prompt" not in result["requested_jsr_packages"]
    assert result["metadata_presence_is_not_complete_dependency_coverage"]


def test_inventory_uses_trailing_url_and_records_unknown_files(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "tools"))
    from inspect_cliffy_deno_cache import inventory

    (tmp_path / "metadata").write_text(
        '{"url":"https://jsr.io/@std/io/meta.json"}\n'
        '{"url":"https://jsr.io/@std/assert/meta.json"}')
    (tmp_path / "unknown").write_bytes(b"no URL")
    result = inventory({"imports": {"@std/io": "jsr:@std/io@~0.225.3"}}, tmp_path)
    assert result["missing_package_metadata"] == ["@std/io"]
    assert result["ignored_files"] == 1
    assert "@std/assert" in result["cached_jsr_packages"]
