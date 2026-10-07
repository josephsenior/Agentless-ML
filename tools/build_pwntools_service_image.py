"""Capture public endpoint bytes, then build a separate image without network."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import runpy
from pathlib import Path
import shutil
import subprocess
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
PARENT = 'sha256:35bce93dd151739b946cd6a9c01258591be30a723729d1b367855480c5ed1529'
SOURCES = (
    ('pypi.json', 'https://pypi.org/simple/pwntools/', {'Accept': 'application/vnd.pypi.simple.v1+json'}),
    ('robots.txt', 'https://httpbingo.org/robots.txt', {}),
)


def verify_pins(records):
    pins = json.loads((ROOT / 'experiments/deepswe/pwntools/service-snapshots.json').read_text())
    expected = {record['file']: record for record in pins['snapshots']}
    if len(records) != len(expected) or {record['file'] for record in records} != set(expected):
        raise ValueError('Unexpected pinned inventory')
    for record in records:
        if any(record[key] != expected[record['file']][key] for key in ('url', 'bytes', 'sha256')):
            raise ValueError('Public bytes differ from reviewed snapshot pins')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--image', default='agentless-ml/pwntools-services:2026-10-08')
    parser.add_argument('--snapshots', type=Path, help='reuse an existing verified capture without network')
    args = parser.parse_args()
    parent = subprocess.check_output(['docker', 'image', 'inspect', 'agentless-ml/pwntools-ssh-aligned:2026-10-08', '--format', '{{.Id}}'], text=True).strip()
    if parent != PARENT:
        raise ValueError('SSH-aligned parent differs from reviewed image')
    destination = args.destination.resolve()
    destination.mkdir(parents=True, exist_ok=False)
    snapshots = destination / 'snapshots'
    snapshots.mkdir()
    records = []
    if args.snapshots:
        source_snapshots = args.snapshots.resolve()
        verifier = runpy.run_path(str(ROOT / 'experiments/deepswe/pwntools/offline-services.py'))
        verifier['load_snapshots'](source_snapshots)
        manifest = json.loads((source_snapshots / 'manifest.json').read_text())
        if manifest['parent_image'] != parent:
            raise ValueError('Snapshot parent differs')
        for filename in ('pypi.json', 'robots.txt', 'manifest.json'):
            shutil.copyfile(source_snapshots / filename, snapshots / filename)
        records = manifest['snapshots']
    for filename, url, headers in (() if args.snapshots else SOURCES):
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as response:
            data = response.read(2_000_001)
            if response.status != 200 or len(data) > 2_000_000 or response.url != url:
                raise ValueError('Unexpected public response')
            record = {'file': filename, 'url': url, 'request_headers': headers,
                      'content_type': response.headers.get('Content-Type'),
                      'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
                      'retrieved_utc': datetime.now(timezone.utc).isoformat()}
        (snapshots / filename).write_bytes(data)
        records.append(record)
    verify_pins(records)
    manifest = {'condition': 'offline-service diagnostic - modified environment', 'parent_image': parent, 'snapshots': records}
    (snapshots / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    source = ROOT / 'experiments/deepswe/pwntools'
    for filename in ('offline-services.py', 'setup-offline-services.sh'):
        shutil.copyfile(source / filename, destination / filename)
    # Resolve the parent immutably even if another process changes its tag.
    recipe = (source / 'Dockerfile.services').read_text().replace(
        'FROM agentless-ml/pwntools-ssh-aligned:2026-10-08',
        'FROM agentless-ml/pwntools-ssh-aligned:2026-10-08@' + parent)
    (destination / 'Dockerfile').write_text(recipe, encoding='utf-8')
    subprocess.run(['docker', 'build', '--network=none', '-t', args.image, str(destination)], check=True)
    identity = subprocess.check_output(['docker', 'image', 'inspect', args.image, '--format', '{{.Id}}'], text=True).strip()
    (destination / 'image.json').write_text(json.dumps({'image': args.image, 'id': identity}, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'artifacts': str(destination), 'image_id': identity, **manifest}, indent=2))


if __name__ == '__main__':
    main()
