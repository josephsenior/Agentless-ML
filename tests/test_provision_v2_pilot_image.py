import hashlib
import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def module(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'tools'))
    return importlib.import_module('provision_v2_pilot_image')


def test_manifest_bytes_must_match_public_digest(module):
    raw = b'{"layers":[],"config":{}}'
    descriptor = dict(digest='sha256:' + hashlib.sha256(raw).hexdigest(), size=len(raw))
    assert module.verified_manifest(raw + b'\n', descriptor)[0] == raw
    with pytest.raises(ValueError, match='digest'):
        module.verified_manifest(raw + b'changed', descriptor)
    with pytest.raises(ValueError, match='size'):
        module.verified_manifest(raw, {**descriptor, 'size': 0})


def test_index_selection_ignores_attestations_and_rejects_ambiguity(module):
    image = dict(digest='sha256:' + 'a' * 64, platform={'os': 'linux', 'architecture': 'amd64'})
    attestation = dict(digest='sha256:' + 'b' * 64, platform={'os': 'unknown', 'architecture': 'unknown'})
    assert module.select_linux_amd64({'manifests': [image, attestation]}) == image
    for entries in ([], [attestation], [image, image]):
        with pytest.raises(ValueError, match='exactly one'):
            module.select_linux_amd64({'manifests': entries})


def test_legacy_and_containerd_identity_are_both_verified(module):
    metadata = dict(Id='config', Os='linux', Architecture='amd64', RepoDigests=['repo@manifest'])
    assert module.verify_local_identity(metadata, 'manifest', 'config', 'repo@manifest') == 'config-digest-legacy-store'
    modern = {**metadata, 'Id': 'manifest', 'Descriptor': {'digest': 'manifest'}}
    assert module.verify_local_identity(modern, 'manifest', 'config', 'repo@manifest') == 'manifest-digest-containerd-store'
    for bad in ({**modern, 'Descriptor': {'digest': 'wrong'}},
                {**modern, 'Id': 'unknown'}, {**modern, 'RepoDigests': []},
                {**modern, 'Architecture': 'arm64'}, {**metadata, 'Id': 'manifest'}):
        with pytest.raises(ValueError):
            module.verify_local_identity(bad, 'manifest', 'config', 'repo@manifest')


def test_inspect_only_never_pulls_tags_or_probes(module, monkeypatch, tmp_path):
    task = SimpleNamespace(instance_id='selected', base_commit='a' * 40,
                           repository_url='https://github.com/example/repo',
                           container_image='ghcr.io/scaleapi/swe-bench_pro-v2:selected')
    dataset = SimpleNamespace(load_tasks=lambda **kwargs: [task])
    monkeypatch.setattr(module, 'SWEbenchProV2Dataset', lambda *args: dataset)
    monkeypatch.setattr(module, 'SWEbenchProDataset', lambda *args: None)
    raw = b'{"layers":[{"size":123}],"config":{"digest":"sha256:config"}}'
    descriptor = dict(digest='sha256:' + hashlib.sha256(raw).hexdigest(), size=len(raw))
    calls = []

    def inspect(argv, **kwargs):
        calls.append(argv)
        assert argv[:4] == ['docker', 'buildx', 'imagetools', 'inspect']
        return raw if '--raw' in argv else json.dumps(descriptor).encode()

    monkeypatch.setattr(module.subprocess, 'check_output', inspect)
    monkeypatch.setattr(module.subprocess, 'run', lambda *a, **kw: pytest.fail('no Docker mutations'))
    monkeypatch.setattr(module, 'pilot_task', lambda *a, **kw: pytest.fail('no container probe'))
    output = tmp_path / 'preflight'
    monkeypatch.setattr('sys.argv', ['provision', '--task-id', 'selected', '--v1-parquet', 'unused',
                                   '--v2-tasks', 'unused', '--output', str(output), '--inspect-only'])
    module.main()
    assert len(calls) == 2
    assert json.loads((output / 'preflight.json').read_text())['compressed_layer_bytes'] == 123
    assert not (output / 'result.json').exists()
