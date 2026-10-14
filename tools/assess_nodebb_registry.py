"""Capture public registry responses used by NodeBB's plugins page and tests.

HTTPS verifies the transport; recorded SHA-256 values pin these captured bytes,
not a historical registry release or an independently published checksum.
No service is built and no public tests are run by this assessment.
"""
import argparse
from datetime import UTC, datetime
import hashlib
import json
import math
from pathlib import Path
from urllib.request import Request, urlopen

ENDPOINTS = (
    ('compatible', 'https://packages.nodebb.org/api/v1/plugins?version=4.1.0'),
    ('all', 'https://packages.nodebb.org/api/v1/plugins'),
    ('trending', 'https://packages.nodebb.org/api/v1/analytics/top/week'),
    ('markdown', 'https://packages.nodebb.org/api/v1/plugins/nodebb-plugin-markdown'),
)
MAX_BYTES = 8 * 1024 * 1024


def validate_payload(kind, payload):
    if kind == 'markdown':
        detail = payload.get('payload') if isinstance(payload, dict) else None
        if not isinstance(detail, dict) or detail.get('name') != 'nodebb-plugin-markdown':
            raise ValueError('plugin detail lacks the requested markdown payload')
        if not isinstance(detail.get('latest'), str) or not detail['latest']:
            raise ValueError('plugin detail lacks its published latest version')
        return 1
    if not isinstance(payload, list):
        raise ValueError('registry response must be a JSON array')
    for entry in payload:
        if not isinstance(entry, dict):
            raise ValueError('registry entries must be objects')
        key = 'label' if kind == 'trending' else 'name'
        if not isinstance(entry.get(key), str) or not entry[key]:
            raise ValueError(f'registry entry lacks {key}')
        if kind == 'trending':
            value = entry.get('value')
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise ValueError('trending value must be a finite nonnegative number')
    return len(payload)


def capture(kind, url, output):
    request = Request(url, headers={'Accept': 'application/json', 'User-Agent': 'NodeBB/4.x (registry snapshot assessment)'})
    with urlopen(request, timeout=30) as response:
        final_url = response.geturl()
        if response.status != 200 or not final_url.startswith('https://packages.nodebb.org/'):
            raise ValueError('unexpected registry status or redirected origin')
        if response.headers.get_content_type() != 'application/json':
            raise ValueError('registry did not return application/json')
        content = response.read(MAX_BYTES + 1)
        if len(content) > MAX_BYTES:
            raise ValueError('registry response exceeds capture limit')
        count = validate_payload(kind, json.loads(content))
        headers = {key: response.headers.get(key) for key in ('Date', 'ETag', 'Last-Modified', 'Content-Type')}
    digest = hashlib.sha256(content).hexdigest()
    filename = kind + '.json'
    (output / filename).write_bytes(content)
    if hashlib.sha256((output / filename).read_bytes()).hexdigest() != digest:
        raise ValueError('saved snapshot does not match downloaded bytes')
    return dict(kind=kind, url=url, final_url=final_url, status=200,
                captured_at=datetime.now(UTC).isoformat(), headers=headers,
                bytes=len(content), entries=count, sha256=digest, file=filename)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    records = []
    for kind, url in ENDPOINTS:
        try:
            records.append(capture(kind, url, args.output))
        except (OSError, ValueError) as error:
            records.append(dict(kind=kind, url=url, error=str(error)))
    evidence = dict(condition='Public NodeBB registry data assessment',
                    snapshots_verified=all('sha256' in row for row in records),
                    records=records, historical_snapshot=False,
                    upstream_published_checksums=False, service_built=False,
                    tests_run=False, baseline_ready=False)
    (args.output / 'assessment.json').write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(evidence, indent=2))
    if not evidence['snapshots_verified']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
