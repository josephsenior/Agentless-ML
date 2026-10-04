"""The audit must not mistake a supported tree for a validated baseline."""

import importlib.util
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from agentless_ml.workspace import WorkspaceError

SPEC = importlib.util.spec_from_file_location(
    "repository_triage", Path(__file__).resolve().parents[1] / "tools" / "triage_deepswe_repositories.py")
triage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(triage)


@pytest.mark.parametrize("path,target,kind", [
    ("link", "file.py", "file"),
    ("docs/link", "../file.py", "file"),
    ("link", "docs", "directory"),
    ("link", ".", "directory"),
    ("link", "other-link", "symlink"),
    ("link", "vendor", "submodule"),
    ("link", "absent", "missing_target"),
    ("link", "../outside", "outside_checkout"),
    ("link", "/etc/passwd", "absolute_target"),
    ("link", "C:/outside", "absolute_target"),
    ("link", "..\\outside", "nonportable_target"),
])
def test_direct_target_classification_never_follows_host_links(path, target, kind):
    entries = {"file.py": {"mode": "100644"}, "docs/readme.md": {"mode": "100644"},
               "other-link": {"mode": "120000"}, "vendor": {"mode": "160000"}}
    assert triage.direct_target(path, target, entries)["direct_target_kind"] == kind


def test_latest_record_wins_without_changing_the_survey(tmp_path):
    survey = tmp_path / "survey.jsonl"
    text = '\n'.join(json.dumps(r) for r in [
        {"task_id": "example", "status": "unsupported_repository"},
        {"task_id": "example", "status": "ready"},
    ])
    survey.write_text(text, encoding="utf-8")
    assert triage.latest_records(survey)["example"]["status"] == "ready"
    assert survey.read_text(encoding="utf-8") == text


def record(task_id="example"):
    return {"task_id": task_id, "base_commit": "a" * 40,
            "status": "unsupported_repository", "message": "old restriction"}


@pytest.mark.parametrize("task_id", ["../outside", "/outside", "C:\\outside", ".", ".."])
def test_survey_ids_cannot_escape_repository_root(tmp_path, task_id):
    with pytest.raises(ValueError):
        triage.inspect_record(record(task_id), tmp_path)


def test_missing_repository_is_not_cloned_or_marked_ready(tmp_path, monkeypatch):
    verify = Mock()
    monkeypatch.setattr(triage, "verify_sealed_repository", verify)
    result = triage.inspect_record(record(), tmp_path)
    assert result["preflight"] == "missing_repository"
    verify.assert_not_called()
    assert not (tmp_path / "example").exists()
    assert "status" not in result


def test_cli_writes_only_requested_evidence_not_the_survey(tmp_path, monkeypatch):
    survey = tmp_path / "survey.jsonl"
    original = json.dumps(record()) + "\n"
    survey.write_text(original, encoding="utf-8")
    output = tmp_path / "audit.json"
    monkeypatch.setattr(triage.sys, "argv", [
        "triage", "--survey", str(survey), "--repositories", str(tmp_path / "repos"),
        "--output", str(output)])
    assert triage.main() == 0
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["counts"] == {"missing_repository": 1}
    assert result["baseline_counts"] == {"unsupported_repository": 1}
    assert survey.read_text(encoding="utf-8") == original
    assert not (tmp_path / "repos").exists()


@pytest.mark.parametrize("timeout", ["0", "-1", "nan", "inf"])
def test_cli_rejects_invalid_timeouts_before_any_inspection(monkeypatch, timeout):
    monkeypatch.setattr(triage.sys, "argv", [
        "triage", "--survey", "not-read.jsonl", "--repositories", "not-read",
        "--timeout-seconds", timeout])
    with pytest.raises(SystemExit) as error:
        triage.main()
    assert error.value.code == 2


@pytest.mark.parametrize("output", ["survey.jsonl", "repos/example/audit.json"])
def test_output_cannot_mutate_survey_or_repository_collection(tmp_path, monkeypatch, output):
    survey = tmp_path / "survey.jsonl"
    survey.write_text(json.dumps(record()) + "\n", encoding="utf-8")
    original = survey.read_bytes()
    monkeypatch.setattr(triage.sys, "argv", [
        "triage", "--survey", str(survey), "--repositories", str(tmp_path / "repos"),
        "--output", str(tmp_path / output)])
    with pytest.raises(SystemExit) as error:
        triage.main()
    assert error.value.code == 2
    assert survey.read_bytes() == original
    assert not (tmp_path / "repos").exists()


def test_a_failed_seal_is_not_bypassed(tmp_path, monkeypatch):
    (tmp_path / "example").mkdir()
    monkeypatch.setattr(triage, "verify_sealed_repository", Mock(side_effect=WorkspaceError("later commits")))
    provider = Mock()
    monkeypatch.setattr(triage, "LocalGitWorkspaceProvider", provider)
    result = triage.inspect_record(record(), tmp_path)
    assert result["preflight"] == "seal_failed"
    assert result["message"] == "later commits"
    provider.assert_not_called()


def test_accepted_tree_creates_no_checkout_and_claims_no_readiness(tmp_path, monkeypatch):
    (tmp_path / "example").mkdir()
    monkeypatch.setattr(triage, "verify_sealed_repository", Mock())
    monkeypatch.setattr(triage, "tree_entries", Mock(return_value=[
        {"path": "file.py", "mode": "100644", "kind": "blob", "oid": "b" * 40},
        {"path": "link", "mode": "120000", "kind": "blob", "oid": "c" * 40},
        {"path": "vendor", "mode": "160000", "kind": "commit", "oid": "d" * 40},
    ]))
    monkeypatch.setattr(triage, "git_read", Mock(return_value=b"file.py"))
    provider = Mock(paths={"file.py", "vendor"}, symlink_paths={"link"})
    monkeypatch.setattr(triage, "LocalGitWorkspaceProvider", Mock(return_value=provider))
    result = triage.inspect_record(record(), tmp_path)
    assert result["preflight"] == "accepted_by_current_workspace"
    assert result["excluded_symlink_paths"] == 1
    assert result["special_entries"][0]["direct_target_kind"] == "file"
    provider.create.assert_not_called()
    assert "status" not in result
