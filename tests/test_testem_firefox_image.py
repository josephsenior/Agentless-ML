from pathlib import Path
import hashlib
import json


def test_offline_startup_retains_protections(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]/'tools'))
    from check_testem_firefox_startup import docker_args,STARTUP
    args=docker_args('sha256:example','owned-name')
    for value in ('--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges',
                  '--memory=8192m','--memory-swap=8192m','--cpus=2','--pids-limit=2048'):
        assert value in args
    assert '--headless' in STARTUP and '--screenshot' in STARTUP
    assert 'MOZ_DISABLE' not in STARTUP and '--no-sandbox' not in STARTUP


def test_dockerfile_is_pinned_no_download_and_preserves_versions():
    text=(Path(__file__).resolve().parents[1]/'experiments/deepswe/testem/Dockerfile.firefox').read_text()
    assert '@sha256:fce2e9ebe359b36b031e0b772159884795fc8383a047bc50eaa46c20fa06e4f6' in text.splitlines()[0]
    assert 'dpkg --unpack /opt/agentless-firefox-seed/debs/*.deb' in text
    assert 'dpkg --configure --pending' in text
    assert "libudev1)\" = '252.39-1~deb12u1'" in text
    assert "libsystemd0)\" = '252.39-1~deb12u1'" in text
    assert 'apt-get update' not in text


def test_stage_copies_only_explicit_verified_set(monkeypatch,tmp_path):
    root=Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root/'tools'))
    import build_testem_firefox_image as builder
    manifest=json.loads(builder.MANIFEST.read_text())
    audit=tmp_path/'audit';(audit/'debs').mkdir(parents=True)
    for item in manifest['packages']:
        item.update(bytes=0,sha256=hashlib.sha256(b'').hexdigest())
        (audit/'debs'/item['artifact']).write_bytes(b'')
    (audit/'debs'/'unselected-upgrade.deb').write_bytes(b'not selected')
    (audit/builder.ARCHIVE).write_bytes(b'fixture')
    manifest['firefox_sha512']=hashlib.sha512(b'fixture').hexdigest()
    monkeypatch.setattr(builder,'OUT',audit)
    context=tmp_path/'context';context.mkdir()
    builder.stage(manifest,context)
    assert len(list((context/'seed/debs').glob('*.deb')))==71
    assert not (context/'seed/debs/unselected-upgrade.deb').exists()
