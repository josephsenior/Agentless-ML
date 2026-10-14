import hashlib
import importlib
from pathlib import Path

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
