import hashlib
import json
from pathlib import Path

import pytest


def test_selected_set_refuses_upgrades_and_duplicate_names(monkeypatch):
    root=Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root/'tools'))
    from verify_testem_no_upgrade import validate_selection
    candidate=json.loads((root/'experiments/deepswe/testem_no_upgrade_candidate_2026_10_09.json').read_text())
    assert len(validate_selection(candidate))==71
    original=candidate['packages'][0]['package']
    candidate['packages'][0]['package']=candidate['packages'][1]['package']
    with pytest.raises(ValueError): validate_selection(candidate)
    candidate['packages'][0]['package']=original
    candidate['packages'][0]['package']='libudev1'
    with pytest.raises(ValueError): validate_selection(candidate)


def test_changed_archive_refused(monkeypatch,tmp_path):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]/'tools'))
    from verify_testem_no_upgrade import check_artifact
    path=tmp_path/'archive.deb'
    path.write_bytes(b'abc')
    pin={'bytes':3,'sha256':hashlib.sha256(b'abc').hexdigest()}
    check_artifact(path,pin)
    pin['sha256']='0'*64
    with pytest.raises(ValueError): check_artifact(path,pin)


def test_inspector_uses_only_explicit_selection(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]/'tools'))
    from verify_testem_no_upgrade import INSPECT
    assert "for p in selection['packages']" in INSPECT
    assert "glob('*.deb')" not in INSPECT
    assert "['dpkg-deb','-x'" in INSPECT
    assert "['readelf','-d'" in INSPECT
    assert "apt-get" not in INSPECT


def test_completed_manifest_keeps_static_and_runtime_results_separate():
    root=Path(__file__).resolve().parents[1]
    report=json.loads((root/'experiments/deepswe/testem_no_upgrade_verified_2026_10_09.json').read_text())
    assert len(report['packages'])==71
    assert all(p['artifact_downloaded_and_verified'] for p in report['packages'])
    assert report['pending_download_and_checksum_verification']==[]
    assert report['static_coverage_passed'] and report['static_missing_library_names']==[]
    assert report['static_elf_files_inspected']==143
    assert not report['browser_runtime_verified'] and not report['image_built'] and not report['tests_run']
