"""Build only the verified two-asset diagnostic image, offline."""

import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from run_testem_firefox_baseline import ROOT, IMAGE as PARENT

TAG = 'agentless-ml/testem-offline-qunit:2026-10-09'
PARENT_TAG = 'agentless-ml/testem-firefox:2026-10-09'
RESULTS = ROOT.parent / 'output/deepswe-survey/testem-offline-qunit'
MANIFEST = ROOT / 'experiments/deepswe/testem_qunit_assets_verified_2026_10_09.json'
CAPTURE = ROOT.parent / 'output/deepswe-survey/testem-qunit-audit-2026-10-09'


def stage(context):
    manifest = json.loads(MANIFEST.read_text())
    if len(manifest['assets']) != 2 or not all(asset['exact_byte_match'] for asset in manifest['assets']):
        raise ValueError('Requires the exact verified two-asset manifest')
    for asset in manifest['assets']:
        pin = asset['cdn']
        if pin['file'] not in ('qunit-1.20.0.js', 'qunit-1.20.0.css'):
            raise ValueError('Unexpected asset filename')
        data = (CAPTURE / pin['file']).read_bytes()
        if len(data) != pin['bytes'] or hashlib.sha256(data).hexdigest() != pin['sha256']:
            raise ValueError('Captured public asset changed')
        shutil.copyfile(CAPTURE / pin['file'], context / pin['file'])
    for source, target in [('offline-qunit.py', 'offline-qunit.py'), ('Dockerfile.qunit', 'Dockerfile')]:
        shutil.copyfile(ROOT / 'experiments/deepswe/testem' / source, context / target)


def main():
    actual = subprocess.check_output(['docker', 'image', 'inspect',
        PARENT_TAG, '--format', '{{.Id}}'], text=True).strip()
    if actual != PARENT:
        raise ValueError('Local parent tag does not match verified Firefox image')
    if subprocess.run(['docker', 'image', 'inspect', TAG], capture_output=True).returncode == 0:
        raise ValueError('Refusing to overwrite an existing diagnostic image tag')
    RESULTS.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='testem-offline-qunit-') as temporary:
        context = Path(temporary)
        stage(context)
        result = subprocess.run(['docker', 'build', '--pull=false', '--network=none', '-t', TAG, str(context)],
                                capture_output=True, text=True, timeout=300)
        (RESULTS / 'build.stdout.log').write_text(result.stdout)
        (RESULTS / 'build.stderr.log').write_text(result.stderr)
        if result.returncode:
            raise RuntimeError('Offline asset image build failed; retained build logs')
    image = subprocess.check_output(['docker', 'image', 'inspect', TAG, '--format', '{{.Id}}'], text=True).strip()
    evidence = {'condition': 'modified environment: offline public-asset delivery',
        'parent_image_id': PARENT, 'image_id': image, 'tag': TAG,
        'network_during_build': 'none', 'manifest_sha256': hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
        'assets': json.loads(MANIFEST.read_text())['assets'], 'benchmark_tests_run': False,
        'official_survey_updated': False}
    (RESULTS / 'build.json').write_text(json.dumps(evidence, indent=2) + '\n')
    print(json.dumps(evidence, indent=2))


if __name__ == '__main__':
    main()
