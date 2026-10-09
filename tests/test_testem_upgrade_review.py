from pathlib import Path
import json


def test_plan_parser_distinguishes_new_and_upgraded_packages(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'tools'))
    from review_testem_library_upgrades import selected_packages
    assert selected_packages('Inst libudev1 [252.39-1~deb12u1] (252.39-1~deb12u2 Debian [amd64])\n'
                             'Inst dbus-x11 (1.14.10-1~deb12u1 Debian [amd64])\n'
                             'Conf dbus-x11 (1.14.10-1~deb12u1 Debian [amd64])\n') == {
        'libudev1':'252.39-1~deb12u2','dbus-x11':'1.14.10-1~deb12u1'}


def test_review_is_offline_simulation_and_control_extraction(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'tools'))
    from review_testem_library_upgrades import REVIEW
    assert "'--simulate','--no-install-recommends'" in REVIEW
    assert "'libudev1=252.39-1~deb12u1'" in REVIEW
    assert "'libsystemd0=252.39-1~deb12u1'" in REVIEW
    assert "'dpkg-deb','-e'" in REVIEW
    assert "apt-get update" not in REVIEW


def test_candidate_preserves_libraries_and_marks_unverified_archive():
    root = Path(__file__).resolve().parents[1]
    candidate = json.loads((root/'experiments/deepswe/testem_no_upgrade_candidate_2026_10_09.json').read_text())
    packages = {p['package']:p for p in candidate['packages']}
    assert len(packages) == candidate['new_packages'] == 71
    assert candidate['upgrades'] == candidate['removals'] == 0
    assert not {'libudev1','libsystemd0','systemd','systemd-sysv','libpam-systemd'} & packages.keys()
    assert [p['package'] for p in candidate['packages'] if not p['artifact_downloaded_and_verified']] == ['dbus-x11']
    assert not candidate['image_built'] and not candidate['tests_run']
