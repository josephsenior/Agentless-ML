"""Build/preflight the labelled four-asset image, or run only the unchanged todo test.

Reuses the existing protected runners. No full-schedule option is exposed here;
the old image, records and default runner remain separate.
"""

import argparse
import hashlib
import json
import shutil
import sys

import build_testem_qunit_image as build

ROOT = build.ROOT
RESULTS = ROOT.parent / 'output/deepswe-survey/testem-offline-qunit-todo'
MANIFEST = ROOT / 'experiments/deepswe/testem_qunit_2_9_2_assets_verified_2026_10_10.json'
CAPTURE = ROOT.parent / 'output/deepswe-survey/testem-qunit-2.9.2-audit-2026-10-10'
PARENT = 'sha256:96b08a03e607416b109f7d86186d1cdfe92755483eada98693e67ff5f2feba00'
IMAGE = 'sha256:e12cec1885154964e390345726e5ae53955831965fc1340f1cd5b9f11220328f'
TEST = '^ci mode app handles todos correctly$'


def stage(context):
    assets = json.loads(MANIFEST.read_text())['assets']
    expected = {'qunit-2.9.2.js', 'qunit-2.9.2.css'}
    if len(assets) != 2 or {a['cdn']['file'] for a in assets} != expected:
        raise ValueError('Requires exactly the verified 2.9.2 assets')
    for asset in assets:
        pin = asset['cdn']
        data = (CAPTURE / pin['file']).read_bytes()
        if (not asset['exact_byte_match'] or len(data) != pin['bytes']
                or hashlib.sha256(data).hexdigest() != pin['sha256']):
            raise ValueError('Captured asset no longer matches the reviewed manifest')
        shutil.copyfile(CAPTURE / pin['file'], context / pin['file'])
    sources = ROOT / 'experiments/deepswe/testem'
    for source, target in [('offline-qunit.py', 'offline-qunit-base.py'),
                           ('offline-qunit-todo.py', 'offline-qunit.py'),
                           ('Dockerfile.qunit-todo', 'Dockerfile')]:
        shutil.copyfile(sources / source, context / target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('build', 'preflight', 'test'))
    action = parser.parse_args().action
    if action == 'build':
        build.PARENT = PARENT
        build.PARENT_TAG = 'agentless-ml/testem-offline-qunit:2026-10-09'
        build.TAG = 'agentless-ml/testem-offline-qunit-todo:2026-10-10'
        build.RESULTS, build.MANIFEST, build.stage = RESULTS, MANIFEST, stage
        build.main()
    elif action == 'preflight':
        import check_testem_qunit_delivery as preflight
        preflight.RESULTS = RESULTS
        return preflight.main()
    else:
        import diagnose_testem_firefox as diagnostic
        import run_testem_qunit_public_test as public
        diagnostic.TEST = public.TEST = TEST
        public.RESULTS = RESULTS
        public.IMAGE = IMAGE
        # The shared runner parses argv too. Never forward a full-suite switch.
        sys.argv = [sys.argv[0]]
        public.main()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
