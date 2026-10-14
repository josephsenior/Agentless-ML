"""Build a separate labelled NodeBB image from the reviewed local captures."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'experiments/swe_bench_pro/v2_js_nodebb_upload_path/registry-snapshots-2026-10-14.json'
PARENT = 'sha256:cc8c9217344bf50df0a4276abad046538bb20e5c2f2815a1b2e201871c5cf364'
PARENT_REF = 'ghcr.io/scaleapi/swe-bench_pro-v2@' + PARENT
TAG = 'agentless-ml/nodebb-registry-snapshot:2026-10-14'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    parent = subprocess.check_output(['docker', 'image', 'inspect', PARENT, '--format', '{{.Id}}'], text=True).strip()
    if parent != PARENT:
        raise ValueError('parent image differs from pin')
    if subprocess.check_output(['docker', 'image', 'inspect', PARENT_REF, '--format', '{{.Id}}'], text=True).strip() != PARENT:
        raise ValueError('registry-digest parent reference differs from local pin')
    if subprocess.run(['docker', 'image', 'inspect', TAG], capture_output=True).returncode == 0:
        raise ValueError('diagnostic image tag already exists; preserve the earlier build')
    manifest = json.loads(MANIFEST.read_bytes())
    source = (ROOT / manifest['local_snapshot_directory']).resolve(strict=True)
    records = manifest['assessment']['records']
    if {row['file'] for row in records} != {'compatible.json', 'all.json', 'trending.json', 'markdown.json'} or len(records) != 4:
        raise ValueError('unexpected snapshot inventory')
    for row in records:
        content = (source / row['file']).read_bytes()
        if len(content) != row['bytes'] or hashlib.sha256(content).hexdigest() != row['sha256']:
            raise ValueError('local snapshot differs from reviewed pin')
    destination = args.destination.resolve()
    destination.mkdir(parents=True, exist_ok=False)
    snapshots = destination / 'snapshots'
    snapshots.mkdir()
    for row in records:
        shutil.copyfile(source / row['file'], snapshots / row['file'])
    shutil.copyfile(MANIFEST, snapshots / 'manifest.json')
    for filename in ('nodebb_registry_service.cjs', 'verify_nodebb_registry_service.cjs'):
        shutil.copyfile(ROOT / 'tools' / filename, destination / filename)
    shutil.copyfile(MANIFEST.parent / 'Dockerfile.registry', destination / 'Dockerfile')
    subprocess.run(['docker', 'build', '--pull=false', '--network=none',
                    '--build-arg', f'PARENT_IMAGE={PARENT_REF}', '--tag', TAG, str(destination)], check=True, timeout=600)
    metadata = json.loads(subprocess.check_output(['docker', 'image', 'inspect', TAG]))[0]
    parent_metadata = json.loads(subprocess.check_output(['docker', 'image', 'inspect', PARENT]))[0]
    layers = parent_metadata['RootFS']['Layers']
    if metadata['RootFS']['Layers'][:len(layers)] != layers:
        raise ValueError('supplemented image does not retain the pinned parent layers')
    result = dict(condition=manifest['proposed_service']['label'], image_id=metadata['Id'],
                  tag=TAG, parent_image=PARENT, parent_ref=PARENT_REF,
                  manifest_sha256=hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
                  copied_files_sha256={path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                                       for path in destination.iterdir() if path.is_file()},
                  service_verified=False, tests_run=False, baseline_ready=False)
    (destination / 'build.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
