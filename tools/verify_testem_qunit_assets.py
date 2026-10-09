"""Verify exact public framework assets; never build an image or run tests."""

import base64
import hashlib
import json
import re
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT.parent / 'output/deepswe-survey/testem-qunit-audit-2026-10-09'
COMMIT = 'e943ac9e80d7d46d929fea6ea3135473335650a3'
PUBLISHER_SRI = 'sha256-V2xxF5gfriI9QS6U5ToXbBJPXjpNwyG51W1YrmgAFcA='
INDEX = 'https://releases.jquery.com/qunit/'


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = {}

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            item = dict(attrs)
            self.links.setdefault(item.get('href'), []).append(item.get('data-hash'))


def fetch(url, filename):
    request = urllib.request.Request(url, headers={'User-Agent': 'Agentless-ML-public-asset-audit'})
    with urllib.request.urlopen(request, timeout=30) as response:
        if response.url != url or response.status != 200:
            raise ValueError('Unexpected redirect or HTTP status: ' + url)
        data = response.read(2_000_001)
        if not data or len(data) > 2_000_000:
            raise ValueError('Empty or oversized public asset')
        (OUT / filename).write_bytes(data)
        return data, {'url': url, 'status': response.status, 'content_type': response.headers.get('Content-Type'),
                      'file': filename, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def verify_asset(data, reference, *, sri=None):
    if data != reference:
        raise ValueError('CDN bytes differ from the immutable upstream release file')
    actual = 'sha256-' + base64.b64encode(hashlib.sha256(data).digest()).decode()
    if sri is not None and actual != sri:
        raise ValueError('Publisher SRI mismatch')
    return actual


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    index, index_record = fetch(INDEX, 'publisher-index.html')
    links = Links(); links.feed(index.decode())
    tag, tag_record = fetch('https://api.github.com/repos/qunitjs/qunit/git/ref/tags/1.20.0', 'upstream-tag.json')
    obj = json.loads(tag)['object']
    if obj != {'sha': COMMIT, 'type': 'commit',
               'url': 'https://api.github.com/repos/qunitjs/qunit/git/commits/' + COMMIT}:
        raise ValueError('Release tag no longer resolves to the reviewed commit')
    records = []
    for suffix in ('js', 'css'):
        url = 'https://code.jquery.com/qunit/qunit-1.20.0.' + suffix
        if url not in links.links:
            raise ValueError('Exact asset absent from publisher index')
        sri = PUBLISHER_SRI if suffix == 'js' else None
        if suffix == 'js' and links.links[url] != [PUBLISHER_SRI]:
            raise ValueError('Publisher script SRI changed or is ambiguous')
        data, cdn = fetch(url, 'qunit-1.20.0.' + suffix)
        source, upstream = fetch('https://raw.githubusercontent.com/qunitjs/qunit/' + COMMIT + '/qunit/qunit.' + suffix,
                                 'upstream-qunit.' + suffix)
        actual_sri = verify_asset(data, source, sri=sri)
        records.append({'version': '1.20.0', 'cdn': cdn, 'upstream': upstream,
                        'exact_byte_match': True, 'computed_sri': actual_sri,
                        'publisher_sri': sri, 'publisher_sri_verified': sri is not None,
                        'css_urls': re.findall(r'url\((.*?)\)', data.decode()) if suffix == 'css' else []})
    evidence = {'label': 'verified_public_qunit_assets_offline_delivery_assessment_only',
        'captured_utc': datetime.now(timezone.utc).isoformat(), 'upstream_commit': COMMIT,
        'publisher_index': index_record, 'upstream_tag': tag_record, 'assets': records,
        'trust': 'HTTPS publisher SRI for JavaScript plus exact upstream commit byte comparison for both assets; not a signed release audit',
        'image_built': False, 'service_started': False, 'benchmark_tests_run': False,
        'official_survey_updated': False}
    (OUT / 'verification.json').write_text(json.dumps(evidence, indent=2) + '\n')
    print(json.dumps(evidence, indent=2))


if __name__ == '__main__':
    main()
