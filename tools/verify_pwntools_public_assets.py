"""Download/inspect public libcdb dependencies; never execute them or build an image."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import lzma
import subprocess
import tarfile
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMAGE = 'sha256:168f8c6b98131e2e58a4ba9265ac16b658174636cbb2d2de6493a0778c856318'
HOSTS = {'libc.rip', 'gitlab.com', 'debuginfod.ubuntu.com', 'debuginfod.debian.net',
         'debuginfod.elfutils.org', 'deb.debian.org', 'snapshot.debian.org',
         'snapshot-cloudflare.debian.org', 'archive.ubuntu.com', 'security.ubuntu.com',
         'old-releases.ubuntu.com', 'launchpad.net', 'launchpadlibrarian.net',
         'snapshot.ubuntu.com'}
ELF_INSPECTOR = '''import io,json,sys
from elftools.elf.elffile import ELFFile
from elftools.elf.sections import NoteSection,SymbolTableSection
elf=ELFFile(io.BytesIO(sys.stdin.buffer.read()))
notes=[note['n_desc'] for section in elf.iter_sections() if isinstance(section,NoteSection) for note in section.iter_notes() if note['n_type']=='NT_GNU_BUILD_ID']
symbols={symbol.name: symbol['st_value'] for section in elf.iter_sections() if isinstance(section,SymbolTableSection) for symbol in section.iter_symbols() if symbol.name in ('read','system','main_arena')}
print(json.dumps(dict(build_id=notes[0] if notes else None, machine=elf['e_machine'],symbols=symbols)))
'''


def validate_url(url: str) -> None:
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != 'https' or parts.hostname not in HOSTS or parts.username or parts.password or parts.port not in (None, 443):
        raise ValueError('URL outside explicit public HTTPS origins')


class PublicRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        validate_url(newurl)
        return super().redirect_request(request, fp, code, msg, headers, newurl)


def hashes(data: bytes) -> dict[str, str]:
    return {name: hashlib.new(name, data).hexdigest() for name in ('md5', 'sha1', 'sha256')}


def inspect_elf(data: bytes) -> dict:
    if not data.startswith(b'\x7fELF'):
        raise ValueError('Not an ELF file')
    result = subprocess.run(['docker', 'run', '--rm', '-i', '--network=none', '--read-only',
        '--cap-drop=ALL', '--security-opt=no-new-privileges', '--memory=512m', '--cpus=1',
        '--pids-limit=64', '--entrypoint=python', IMAGE, '-c', ELF_INSPECTOR],
        input=data, capture_output=True, timeout=90, check=True)
    return json.loads(result.stdout)


def deb_data(archive: bytes) -> bytes:
    if not archive.startswith(b'!<arch>\n'):
        raise ValueError('Not a Debian ar archive')
    position = 8
    while position + 60 <= len(archive):
        header = archive[position:position + 60]
        size = int(header[48:58].strip())
        name = header[:16].decode().strip().rstrip('/')
        start = position + 60
        if header[58:60] != b'`\n' or start + size > len(archive):
            raise ValueError('Truncated ar member')
        if name.startswith('data.tar'):
            return archive[start:start + size]
        position = start + size + size % 2
    raise ValueError('No data archive')


class Verification:
    def __init__(self, directory: Path):
        self.directory = directory
        self.records: list[dict] = []
        self.opener = urllib.request.build_opener(PublicRedirect())

    def fetch(self, label: str, url: str, params=None, limit=100 * 1024 * 1024):
        print('CHECK ' + label, flush=True)
        record = {'label': label, 'url': url}
        if params is not None:
            record['request_json'] = params
        self.records.append(record)
        try:
            validate_url(url)
            body = None if params is None else json.dumps(params).encode()
            request = urllib.request.Request(url, data=body, headers={'User-Agent': 'Agentless-ML-public-asset-verification', 'Content-Type': 'application/json'})
            with self.opener.open(request, timeout=20) as response:
                data = response.read(limit + 1)
                if len(data) > limit:
                    raise ValueError('Response exceeds inspection size limit')
                record.update(status=response.status, final_url=response.url, bytes=len(data), **hashes(data))
            filename = f'{len(self.records):03d}-{record["sha256"]}.download'
            (self.directory / filename).write_bytes(data)
            record['artifact'] = filename
            return data, record
        except (OSError, ValueError, urllib.error.URLError) as error:
            record['error'] = str(error)
            return None, record


def supplement(check: Verification, previous: Path) -> dict:
    """Try the other provider and publisher debug archives after initial checks."""
    prior = json.loads(previous.read_text())
    for alias in prior['aliases']:
        if alias['ids'] or alias['kind'] == 'libs_id':
            continue
        kind = 'build_id' if alias['kind'] == 'hash' else alias['kind']
        url = f'https://gitlab.com/libcdb/libcdb/-/raw/master/hashes/{kind}/{alias["value"]}'
        for hop in range(6):
            data, record = check.fetch(f'GitLab {kind}:{alias["value"]} hop {hop}', url)
            if not data:
                break
            if data.startswith(b'\x7fELF'):
                record['elf'] = inspect_elf(data)
                actual = record['elf']['build_id'] if kind == 'build_id' else record[kind]
                record['requested_identifier_matches'] = actual == alias['value']
                break
            if data.strip().startswith(b'..'):
                url = urllib.parse.urljoin(url, data.decode().strip())
            else:
                record['verification_error'] = 'Neither ELF nor relative provider link'
                break
    targets = [
        ('69389d485a9793dbe873f0ea2c93e02efaa9aa3d', 'https://archive.ubuntu.com/ubuntu/pool/main/g/glibc/libc6-dbg_2.35-0ubuntu3.1_amd64.deb'),
        ('69389d485a9793dbe873f0ea2c93e02efaa9aa3d', 'https://launchpad.net/ubuntu/+archive/primary/+files/libc6-dbg_2.35-0ubuntu3.1_amd64.deb'),
        ('d1704d25fbbb72fa95d517b883131828c0883fe9', 'https://old-releases.ubuntu.com/ubuntu/pool/main/g/glibc/libc6-dbg_2.36-0ubuntu4_amd64.deb'),
    ]
    found = set()
    for buildid, url in targets:
        if buildid in found:
            continue
        data, record = check.fetch('publisher debug package ' + buildid, url)
        if data:
            with tarfile.open(fileobj=io.BytesIO(deb_data(data)), mode='r:*') as archive:
                expected = buildid[2:] + '.debug'
                member = next((item for item in archive if item.isfile() and Path(item.name).name == expected and '/.build-id/' + buildid[:2] + '/' in item.name), None)
                if member:
                    debug = archive.extractfile(member).read()
                    record['debug_member'] = dict(name=member.name, bytes=len(debug), **hashes(debug), elf=inspect_elf(debug))
                    record['build_id_matches'] = record['debug_member']['elf']['build_id'] == buildid
                    if record['build_id_matches']:
                        found.add(buildid)
                else:
                    record['verification_error'] = 'Required build-ID member not in package'
    return dict(previous_evidence=str(previous), records=check.records,
        image_built=False, downloaded_binaries_executed=False,
        integrity_note='Archive SHA-256 values are measured pins unless a separate publisher checksum is explicitly recorded. Requested content identifiers and debug build IDs are checked independently.')


def complete_symbols(check: Verification, previous: Path) -> dict:
    prior = json.loads(previous.read_text())
    existing = {entry['id'] for entry in prior['libraries']}
    metadata = {}
    for record in prior['records']:
        if record['label'] == 'public symbol-offset lookup' and record.get('artifact'):
            raw = (previous.parent / record['artifact']).read_bytes()
            if hashes(raw)['sha256'] != record['sha256']:
                raise ValueError('Prior query artifact checksum mismatch')
            for item in json.loads(raw):
                metadata[item['id']] = item
    for identity, item in metadata.items():
        if identity in existing:
            continue
        data, record = check.fetch('symbol-query libc ' + identity, item['download_url'])
        if data:
            record['elf'] = inspect_elf(data)
            record['metadata_hashes_match'] = all(record[name] == item[name] for name in ('md5', 'sha1', 'sha256'))
            record['build_id_matches'] = record['elf']['build_id'] == item['buildid']
        data, record = check.fetch('symbol-query symbols ' + identity, item['symbols_url'], limit=4 * 1024 * 1024)
        if data:
            parsed = dict(line.split() for line in data.decode().splitlines())
            record['api_symbols_match'] = all(key in parsed and int(parsed[key], 16) == int(value, 16) for key, value in item['symbols'].items())
    index_targets = [
        ('2.35-0ubuntu3.1', 'https://snapshot.ubuntu.com/ubuntu/20230301T000000Z/dists/jammy-updates/main/binary-amd64/Packages.xz'),
        ('2.36-0ubuntu4', 'https://old-releases.ubuntu.com/ubuntu/dists/kinetic/main/binary-amd64/Packages.xz'),
    ]
    for version, url in index_targets:
        raw, record = check.fetch('publisher package index ' + version, url, limit=20 * 1024 * 1024)
        if raw:
            text = lzma.decompress(raw).decode()
            stanzas = [dict(line.split(': ', 1) for line in block.splitlines() if ': ' in line and not line.startswith(' ')) for block in text.split('\n\n')]
            record['requested_package'] = next((item for item in stanzas if item.get('Package') == 'libc6-dbg' and item.get('Version') == version), None)
            record['signature_verified'] = False
    return dict(previous_evidence=str(previous), query_library_count=len(metadata),
        already_checked_query_ids=sorted(existing.intersection(metadata)), records=check.records,
        image_built=False, downloaded_binaries_executed=False,
        integrity_note='API hash/build-ID matches and publisher archive checksums are recorded distinctly. HTTPS publisher index fetched, but no OpenPGP Release signature verification performed.')


def verify_tool_archives(check: Verification) -> dict:
    packages = [
        ('elfutils', '31e479c38d2eb1a5d134c1d12bf619d1a1a1fa4482b073e95c70021c07443c23'),
        ('libasm1', '7d550ea35716c3f413e0132b4b498492655a2090a65c756f492d11e004aeabc6'),
    ]
    for name, expected in packages:
        url = f'https://deb.debian.org/debian/pool/main/e/elfutils/{name}_0.188-2.1_amd64.deb'
        data, record = check.fetch('unstrip tooling ' + name, url)
        record['expected_sha256'] = expected
        record['checksum_source'] = 'APT-authenticated Debian bookworm package metadata, version 0.188-2.1 amd64'
        if data:
            record['publisher_sha256_matches'] = record['sha256'] == expected
    return dict(records=check.records, image_built=False, packages_installed=False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifacts', type=Path, default=ROOT.parent / 'output/deepswe-survey/pwntools-public-assets-2026-10-07')
    parser.add_argument('--supplement', type=Path, help='Initial evidence to check via fallback providers/archives')
    parser.add_argument('--complete-symbol-data', action='store_true', help='Verify every library in the saved public symbol-query snapshot plus publisher indexes')
    parser.add_argument('--tool-archives', action='store_true', help='Check pinned elfutils/libasm1 archives without installing them')
    args = parser.parse_args()
    args.artifacts.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix='verification-', dir=args.artifacts))
    check = Verification(directory)
    if args.complete_symbol_data and not args.supplement:
        parser.error('--complete-symbol-data requires --supplement')
    if args.tool_archives:
        evidence = verify_tool_archives(check)
        (directory / 'verification.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
        print('EVIDENCE ' + str(directory / 'verification.json'), flush=True)
        return 0
    if args.supplement:
        evidence = complete_symbols(check, args.supplement) if args.complete_symbol_data else supplement(check, args.supplement)
        (directory / 'verification.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
        print('EVIDENCE ' + str(directory / 'verification.json'), flush=True)
        return 0
    prior = json.loads((ROOT / 'experiments/deepswe/pwntools_libcdb_2026_10_07.json').read_text())
    requests = prior['execution']['observations'][0]['literal_public_requests']
    entries = {}
    aliases = []
    for kind, value in requests:
        if value == 'XX':
            continue
        field = {'hash': 'buildid', 'build_id': 'buildid', 'libs_id': 'id'}.get(kind, kind)
        data, record = check.fetch(f'lookup {kind}:{value}', 'https://libc.rip/api/find', {field: value}, limit=8 * 1024 * 1024)
        matches = json.loads(data) if data else []
        record['match_count'] = len(matches)
        aliases.append(dict(kind=kind, value=value, ids=[item['id'] for item in matches]))
        for item in matches:
            entries[item['id']] = item
    symbol_results = []
    for symbols in ({'puts': '0x420', 'printf': '0xc90'}, {'__libc_start_main_ret': '7f89ad926550'}):
        data, record = check.fetch('public symbol-offset lookup', 'https://libc.rip/api/find', {'symbols': symbols}, limit=8 * 1024 * 1024)
        matches = json.loads(data) if data else []
        record['match_count'] = len(matches)
        symbol_results.append(dict(query=symbols, ordered_ids=[item['id'] for item in matches]))
        # select_index=1 is used only by the first example; the second lists IDs.
        if matches and 'puts' in symbols:
            entries[matches[0]['id']] = matches[0]
    verified = []
    for identity, metadata in entries.items():
        data, record = check.fetch('libc ' + identity, metadata['download_url'])
        if data:
            try:
                elf = inspect_elf(data)
                record['elf'] = elf
                record['metadata_hashes_match'] = all(record[name] == metadata[name] for name in ('md5', 'sha1', 'sha256'))
                record['build_id_matches'] = elf['build_id'] == metadata['buildid']
                verified.append(dict(id=identity, metadata=metadata, record=record))
            except (ValueError, subprocess.SubprocessError) as error:
                record['verification_error'] = str(error)
        if metadata.get('symbols_url'):
            symbols, symbol_record = check.fetch('symbols ' + identity, metadata['symbols_url'], limit=4 * 1024 * 1024)
            if symbols:
                parsed = dict(line.split() for line in symbols.decode().splitlines())
                symbol_record['api_symbols_match'] = all(int(parsed[key], 16) == int(value, 16) for key, value in metadata['symbols'].items() if key in parsed)
                symbol_record['missing_api_symbols'] = sorted(set(metadata['symbols']) - set(parsed))
    for buildid in ('69389d485a9793dbe873f0ea2c93e02efaa9aa3d', 'd1704d25fbbb72fa95d517b883131828c0883fe9'):
        for server in ('debuginfod.ubuntu.com', 'debuginfod.debian.net', 'debuginfod.elfutils.org'):
            data, record = check.fetch('debuginfo ' + buildid, f'https://{server}/buildid/{buildid}/debuginfo')
            if data:
                try:
                    record['elf'] = inspect_elf(data)
                    record['build_id_matches'] = record['elf']['build_id'] == buildid
                    if record['build_id_matches']:
                        break
                except (ValueError, subprocess.SubprocessError) as error:
                    record['verification_error'] = str(error)
    package_url = 'https://deb.debian.org/debian/pool/main/g/glibc/libc6_2.36-9+deb12u14_amd64.deb'
    package, record = check.fetch('matching current libc/loader package', package_url)
    record['expected_sha256'] = 'ba4f88f73dbc3ae9055f3c20f4523bfdbaf1ad13ff95e258924f77d20b4fbedf'
    record['checksum_source'] = 'APT-authenticated Debian bookworm package metadata: libc6=2.36-9+deb12u14 amd64'
    if package:
        record['publisher_sha256_matches'] = record['sha256'] == record['expected_sha256']
        with tarfile.open(fileobj=io.BytesIO(deb_data(package)), mode='r:*') as archive:
            members = []
            for member in archive:
                if member.isfile() and Path(member.name).name in ('libc.so.6', 'ld-linux-x86-64.so.2', 'copyright'):
                    data = archive.extractfile(member).read()
                    item = dict(name=member.name, bytes=len(data), **hashes(data))
                    if data.startswith(b'\x7fELF'):
                        item['elf'] = inspect_elf(data)
                    members.append(item)
            record['inspected_members'] = members
    evidence = dict(records=check.records, aliases=aliases, symbol_results=symbol_results, libraries=verified,
        image_built=False, downloaded_binaries_executed=False, runtime_network_enabled=False,
        integrity_note='Computed SHA-256 is a future content pin, not independent publisher authentication. API hashes and build IDs are checked separately; the current Debian package has an APT-authenticated SHA-256.')
    (directory / 'verification.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    print('EVIDENCE ' + str(directory / 'verification.json'), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
