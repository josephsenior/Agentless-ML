"""Provision exactly one pinned public V2 image, then reuse the cheap probe."""
import argparse
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

from agentless_ml.adapters.benchmarks import (
    SWEbenchProDataset, SWEbenchProDatasetPin, SWEbenchProV2Dataset, SWEbenchProV2DatasetPin,
)
from batch_v2_provisioning import ROOT, is_parked, pilot_task


def verified_document(raw, descriptor):
    # Some CLI versions append a terminal newline; accept only bytes whose hash
    # exactly matches the public descriptor, never merely equivalent JSON.
    for content in (raw, raw.rstrip(b'\r\n')):
        if 'sha256:' + hashlib.sha256(content).hexdigest() == descriptor['digest']:
            manifest = json.loads(content)
            if len(content) != descriptor['size']:
                raise ValueError('descriptor size mismatch')
            return content, manifest
    raise ValueError('raw manifest does not match its public digest')


def verified_manifest(raw, descriptor):
    content, manifest = verified_document(raw, descriptor)
    if 'layers' not in manifest:
        raise ValueError('expected a single leaf image manifest')
    return content, manifest


def select_linux_amd64(index):
    matches = [entry for entry in index.get('manifests', [])
               if entry.get('platform', {}).get('os') == 'linux'
               and entry.get('platform', {}).get('architecture') == 'amd64'
               and not entry.get('platform', {}).get('variant')]
    if len(matches) != 1 or not re.fullmatch(r'sha256:[0-9a-f]{64}', matches[0]['digest']):
        raise ValueError('index must have exactly one supported linux/amd64 image')
    return matches[0]


def verify_local_identity(metadata, manifest_digest, config_digest, reference):
    if metadata['Os'] != 'linux' or metadata['Architecture'] != 'amd64':
        raise ValueError('pulled image platform mismatch')
    descriptor = metadata.get('Descriptor', {}).get('digest')
    if descriptor is not None and descriptor != manifest_digest:
        raise ValueError('local manifest descriptor mismatch')
    if metadata['Id'] == manifest_digest and descriptor == manifest_digest:
        identity_kind = 'manifest-digest-containerd-store'
    elif metadata['Id'] == config_digest:
        identity_kind = 'config-digest-legacy-store'
    else:
        raise ValueError('pulled image identity mismatch')
    if reference not in metadata.get('RepoDigests', []):
        raise ValueError('pulled image does not retain the reviewed registry digest')
    return identity_kind


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task-id', required=True)
    parser.add_argument('--v1-parquet', type=Path, required=True)
    parser.add_argument('--v2-tasks', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--reuse-downloaded', action='store_true',
                        help='Verify an already pulled digest and probe it without pulling again')
    parser.add_argument('--inspect-only', action='store_true',
                        help='Verify public manifest and size only; no layers pulled or containers run')
    parser.add_argument('--expected-manifest',
                        help='Require this previously reviewed leaf digest before pulling or probing')
    args = parser.parse_args()
    if args.inspect_only and args.reuse_downloaded:
        parser.error('--inspect-only and --reuse-downloaded are mutually exclusive')
    pin = json.loads((ROOT / 'experiments/swe_bench_pro/v2_corpus_pin.json').read_bytes())
    tasks = SWEbenchProV2Dataset(args.v2_tasks, SWEbenchProV2DatasetPin(
        pin['v2_dataset_revision'], pin['v2_visible_files_sha256'], pin['v2_task_count']),
        SWEbenchProDataset(args.v1_parquet, SWEbenchProDatasetPin(
            pin['v1_dataset_revision'], pin['v1_parquet_sha256'], pin['v1_row_count']))).load_tasks(
                instance_ids=(args.task_id,))
    task = tasks[0]
    if is_parked(task) or not task.container_image.startswith('ghcr.io/scaleapi/swe-bench_pro-v2:'):
        raise ValueError('only a non-parked official V2 image is allowed')
    args.output.mkdir(parents=True, exist_ok=False)
    descriptor = json.loads(subprocess.check_output([
        'docker', 'buildx', 'imagetools', 'inspect', task.container_image,
        '--format', '{{json .Manifest}}'], timeout=60))
    digest = descriptor['digest']
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', digest):
        raise ValueError('invalid manifest digest')
    reference = task.container_image.rsplit(':', 1)[0] + '@' + digest
    raw = subprocess.check_output(['docker', 'buildx', 'imagetools', 'inspect', '--raw', reference], timeout=60)
    content, document = verified_document(raw, descriptor)
    parent_index_digest = None
    if 'manifests' in document:
        parent_index_digest = digest
        (args.output / 'index.json').write_bytes(content)
        descriptor = select_linux_amd64(document)
        digest = descriptor['digest']
        reference = task.container_image.rsplit(':', 1)[0] + '@' + digest
        raw = subprocess.check_output(['docker', 'buildx', 'imagetools', 'inspect', '--raw', reference], timeout=60)
    content, manifest = verified_manifest(raw, descriptor)
    if args.expected_manifest is not None and digest != args.expected_manifest:
        raise ValueError('selected manifest differs from the previously reviewed digest')
    (args.output / 'manifest.json').write_bytes(content)
    compressed = sum(layer['size'] for layer in manifest['layers'])
    free = shutil.disk_usage(ROOT.anchor).free
    preflight = dict(task_id=task.instance_id, base_commit=task.base_commit,
                     parent_index_digest=parent_index_digest,
                     public_tag=task.container_image, manifest_digest=digest,
                     config_digest=manifest['config']['digest'], compressed_layer_bytes=compressed,
                     layers=len(manifest['layers']), host_free_bytes=free,
                     host_reserve_required_bytes=20 * 1024**3,
                     note='Compressed total is not unpacked size or incremental download size; layers may be shared.')
    (args.output / 'preflight.json').write_text(json.dumps(preflight, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(preflight), flush=True)
    if args.inspect_only:
        return
    if compressed > 8 * 1024**3 or free < max(20 * 1024**3, 4 * compressed):
        raise ValueError('image exceeds this bounded pilot download/disk policy; review first')
    if not args.reuse_downloaded:
        print('Pulling exactly one image by verified manifest digest', flush=True)
        with (args.output / 'pull.stdout.log').open('wb') as stdout, (args.output / 'pull.stderr.log').open('wb') as stderr:
            subprocess.run(['docker', 'pull', '--platform=linux/amd64', reference],
                           stdout=stdout, stderr=stderr, check=True, timeout=1200)
    metadata = json.loads(subprocess.check_output(['docker', 'image', 'inspect', reference], timeout=30))[0]
    identity_kind = verify_local_identity(metadata, digest, manifest['config']['digest'], reference)
    existing = subprocess.run(['docker', 'image', 'inspect', task.container_image], capture_output=True, timeout=30)
    if existing.returncode == 0 and json.loads(existing.stdout)[0]['Id'] != metadata['Id']:
        raise ValueError('refuse to replace an existing different local task tag')
    subprocess.run(['docker', 'tag', metadata['Id'], task.container_image], check=True, timeout=30)
    print('Image verified; running only the cheap workspace probe', flush=True)
    probe = pilot_task(task, {task.container_image: metadata['Id']}, {},
                       ROOT.parent / 'benchmarks/swe-bench-pro-v2/repos', args.output)
    evidence = dict(preflight, generated_at=datetime.now(UTC).isoformat(), image_id=metadata['Id'],
                    docker_reported_size_bytes=metadata['Size'], identity_kind=identity_kind,
                    probe=probe, images_pulled=0 if args.reuse_downloaded else 1,
                    public_tests_run=False, full_suites_run=0, model_calls=0, verifier_run=False,
                    official_readiness_changed=False, host_free_after_bytes=shutil.disk_usage(ROOT.anchor).free)
    (args.output / 'result.json').write_text(json.dumps(evidence, indent=2, default=str) + '\n', encoding='utf-8')
    print(json.dumps(dict(image_id=metadata['Id'], compressed_bytes=compressed,
                         docker_reported_size_bytes=metadata['Size'], probe_status=probe['status']), indent=2))
    if probe['status'] != 'workspace_probe_passed_needs_public_plan':
        raise SystemExit('image provisioned but workspace probe did not pass')


if __name__ == '__main__':
    main()
