"""Tarball checks fail closed without installing third-party packages."""
import base64
import hashlib
import importlib
import io
import json
from pathlib import Path
import tarfile

import pytest


@pytest.fixture
def verifier(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'tools'))
    return importlib.import_module('assess_nodebb_imgur').verify_tarball


def fixture_tarball():
    package = {'name': 'example', 'version': '1.0.0',
               'dependencies': {'child': '^1.0.0'},
               'scripts': {'install': 'must-not-run'}}
    payload = json.dumps(package).encode()
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w:gz') as archive:
        member = tarfile.TarInfo('package/package.json')
        member.size = len(payload)
        archive.addfile(member, io.BytesIO(payload))
    content = stream.getvalue()
    metadata = {**package, 'dist': {
        'integrity': 'sha512-' + base64.b64encode(hashlib.sha512(content).digest()).decode(),
        'shasum': hashlib.sha1(content).hexdigest(),
    }}
    return content, metadata


def test_valid_archive_records_but_does_not_execute_install_script(verifier):
    content, metadata = fixture_tarball()
    result = verifier(content, metadata)
    assert result['scripts'] == {'install': 'must-not-run'}
    assert result['package_manifest_verified']
    assert result['integrity_verified'] == ['sha512']


@pytest.mark.parametrize('failure', ['bytes', 'sha1', 'missing-sri', 'identity', 'dependencies'])
def test_rejects_tampered_or_unverifiable_archive(verifier, failure):
    content, metadata = fixture_tarball()
    if failure == 'bytes':
        content += b'tampered'
    elif failure == 'sha1':
        metadata['dist']['shasum'] = '0' * 40
    elif failure == 'missing-sri':
        metadata['dist'].pop('integrity')
    elif failure == 'identity':
        metadata['version'] = '2.0.0'
    else:
        metadata['dependencies'] = {'child': '^2.0.0'}
    with pytest.raises(ValueError):
        verifier(content, metadata)
