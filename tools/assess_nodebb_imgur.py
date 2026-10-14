"""Verify Imgur install/upgrade package trees and the public NodeBB response.

Uses the pinned image's npm CLI on host Node for isolated lock-only resolution.
No package lifecycle scripts, benchmark tests or image builds are run. The
result does not certify npm's full NodeBB-root install/uninstall transaction.
"""
import argparse
import base64
from datetime import UTC, datetime
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen
import uuid

IMAGE = 'sha256:3b4a66b46fa2aa2cc821870fbd9c8a0bd9ec12dae99aaf5449307c7c77ebdf0e'
PACKAGE = 'nodebb-plugin-imgur'
MAX_BYTES = 32 * 1024 * 1024


def download(url, destination, *, host):
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname != host or parsed.username or parsed.password:
        raise ValueError('unexpected public download origin')
    with urlopen(Request(url, headers={'Accept': 'application/json' if not url.endswith('.tgz') else '*/*'}), timeout=30) as response:
        if response.status != 200 or urlparse(response.geturl()).hostname != host or not response.geturl().startswith('https://'):
            raise ValueError('unexpected public response or redirect')
        content = response.read(MAX_BYTES + 1)
        if len(content) > MAX_BYTES:
            raise ValueError('public file exceeds capture limit')
        record = dict(url=url, final_url=response.geturl(), captured_at=datetime.now(UTC).isoformat(),
                      status=response.status, content_type=response.headers.get('Content-Type'),
                      etag=response.headers.get('ETag'), bytes=len(content),
                      sha256=hashlib.sha256(content).hexdigest(), file=str(destination))
    destination.write_bytes(content)
    if hashlib.sha256(destination.read_bytes()).hexdigest() != record['sha256']:
        raise ValueError('saved file differs from downloaded bytes')
    return content, record


def verify_tarball(content, metadata):
    dist = metadata['dist']
    sri = dist.get('integrity', '').split()
    verified = []
    for token in sri:
        algorithm, expected = token.split('-', 1)
        if algorithm not in ('sha512', 'sha384', 'sha256', 'sha1'):
            raise ValueError('unsupported integrity algorithm')
        digest = base64.b64encode(hashlib.new(algorithm, content).digest()).decode()
        if digest != expected:
            raise ValueError('tarball differs from published integrity')
        verified.append(algorithm)
    if not verified:
        raise ValueError('package lacks published SRI')
    if hashlib.sha1(content).hexdigest() != dist['shasum']:
        raise ValueError('tarball differs from published SHA-1')
    with tarfile.open(fileobj=io.BytesIO(content), mode='r:gz') as archive:
        members = [member for member in archive.getmembers() if member.name in ('package/package.json', 'package.json')]
        if len(members) != 1 or not members[0].isfile() or members[0].size > 1024 * 1024:
            raise ValueError('missing or unsafe package manifest')
        package = json.load(archive.extractfile(members[0]))
    if (package['name'], package['version']) != (metadata['name'], metadata['version']):
        raise ValueError('tarball package identity differs from metadata')
    for field in ('dependencies', 'optionalDependencies', 'peerDependencies'):
        if package.get(field, {}) != metadata.get(field, {}):
            raise ValueError(f'tarball {field} differ from published metadata')
    return dict(integrity_verified=verified, sha1_verified=True,
                package_manifest_verified=True, scripts=package.get('scripts', {}),
                engines=package.get('engines', {}))


def capture_npm(output):
    name = 'agentless-nodebb-npm-inspect-' + uuid.uuid4().hex
    tooling = output / 'tooling'
    tooling.mkdir()
    try:
        subprocess.run(['docker', 'create', '--pull=never', '--name', name, '--network=none',
                        '--read-only', '--cap-drop=ALL', '--security-opt=no-new-privileges',
                        '--entrypoint=node', IMAGE, '--version'], check=True, capture_output=True)
        subprocess.run(['docker', 'cp', name + ':/usr/local/lib/node_modules/npm', str(tooling / 'npm')],
                       check=True, capture_output=True, timeout=120)
    finally:
        subprocess.run(['docker', 'rm', '--force', name], capture_output=True, timeout=30)
    cli = tooling / 'npm/bin/npm-cli.js'
    version = subprocess.check_output(['node', str(cli), '--version'], text=True).strip()
    if version != '10.8.2':
        raise ValueError('copied npm differs from the reviewed image toolchain')
    return cli, dict(image_id=IMAGE, npm_version=version,
                     host_node=subprocess.check_output(['node', '--version'], text=True).strip(),
                     cli_sha256=hashlib.sha256(cli.read_bytes()).hexdigest())


def resolve_tree(cli, version, output):
    project = output / ('resolution-' + version)
    project.mkdir()
    (project / 'package.json').write_text(json.dumps(dict(name='agentless-imgur-assessment', version='0.0.0',
                                                        private=True, dependencies={PACKAGE: version})), encoding='utf-8')
    for filename in ('empty-user.npmrc', 'empty-global.npmrc'):
        (project / filename).write_text('', encoding='utf-8')
    env = {key: value for key, value in os.environ.items()
           if not key.lower().startswith('npm_config_') and key not in ('NODE_AUTH_TOKEN', 'NPM_TOKEN')}
    command = ['node', str(cli), 'install', '--package-lock-only', '--ignore-scripts', '--no-audit', '--no-fund',
               '--registry=https://registry.npmjs.org', '--cache=' + str(output / 'resolution-cache'),
               '--userconfig=' + str(project / 'empty-user.npmrc'),
               '--globalconfig=' + str(project / 'empty-global.npmrc'), '--fetch-retries=0', '--fetch-timeout=30000']
    result = subprocess.run(command, cwd=project, env=env, capture_output=True, timeout=300)
    (project / 'stdout.log').write_bytes(result.stdout)
    (project / 'stderr.log').write_bytes(result.stderr)
    if result.returncode:
        raise ValueError(f'isolated resolution failed for {version}; see {project}')
    lock = json.loads((project / 'package-lock.json').read_bytes())
    packages = []
    for location, package in lock['packages'].items():
        if not location:
            continue
        name = location.rsplit('node_modules/', 1)[-1]
        packages.append(dict(name=name, version=package['version'], resolved=package['resolved'],
                             integrity=package['integrity'], dependencies=package.get('dependencies', {}),
                             optional_dependencies=package.get('optionalDependencies', {}),
                             peer_dependencies=package.get('peerDependencies', {}),
                             os=package.get('os'), cpu=package.get('cpu')))
    return dict(root_version=version, packages=packages,
                lock_sha256=hashlib.sha256((project / 'package-lock.json').read_bytes()).hexdigest(),
                lock_file=str(project / 'package-lock.json'))


def record_existing(assessment_path, destination):
    """Recheck saved bytes and write portable evidence, without network or Docker."""
    output = assessment_path.resolve().parent
    evidence = json.loads(assessment_path.read_bytes())
    records = [evidence['npm_packument'], evidence['nodebb_response']]
    for package in evidence['verified_packages']:
        records.extend((package['metadata'], package['tarball']))
        metadata = json.loads(Path(package['metadata']['file']).read_bytes())
        actual = verify_tarball(Path(package['tarball']['file']).read_bytes(), metadata)
        if actual != package['verification']:
            raise ValueError('saved verification differs from replay')
    for record in records:
        path = Path(record['file']).resolve()
        relative = path.relative_to(output)
        content = path.read_bytes()
        if len(content) != record['bytes'] or hashlib.sha256(content).hexdigest() != record['sha256']:
            raise ValueError('saved public asset changed')
        record['file'] = relative.as_posix()
    for resolution in evidence['resolutions']:
        path = Path(resolution['lock_file']).resolve()
        if hashlib.sha256(path.read_bytes()).hexdigest() != resolution['lock_sha256']:
            raise ValueError('saved resolution lock changed')
        resolution['lock_file'] = path.relative_to(output).as_posix()
    detail = json.loads((output / evidence['nodebb_response']['file']).read_bytes())['payload']
    if detail['url'] != 'https://github.com/barisusakli/nodebb-plugin-imgur#readme' or detail['description'] != 'A Plugin that uploads images to imgur':
        raise ValueError('registry fields differ from public test expectations')
    evidence['nodebb_payload'] = detail
    evidence['artifact_directory'] = output.name
    evidence['limitations'] = [
        'Isolated lock-only resolution uses image npm 10.8.2 on Windows Node 22.20.0, not Linux Node 18.20.8.',
        'The full NodeBB-root install, upgrade and uninstall transactions remain unverified.',
        'Current public registry snapshots pin mutable latest; they are not historical benchmark data.',
        'SRI and SHA-1 are verified against HTTPS registry metadata; registry signatures are not verified.',
    ]
    destination.write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(evidence=str(destination), verified_packages=len(evidence['verified_packages']))))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--record-existing', type=Path)
    parser.add_argument('--evidence', type=Path)
    args = parser.parse_args()
    if args.record_existing:
        if args.output or not args.evidence:
            parser.error('--record-existing requires --evidence and excludes --output')
        record_existing(args.record_existing, args.evidence)
        return
    if not args.output or args.evidence:
        parser.error('capture requires --output; --evidence requires --record-existing')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    metadata_directory, tarballs = output / 'metadata', output / 'tarballs'
    metadata_directory.mkdir()
    tarballs.mkdir()
    pack_bytes, pack_record = download('https://registry.npmjs.org/' + PACKAGE, output / 'imgur-packument.json', host='registry.npmjs.org')
    detail_bytes, detail_record = download('https://packages.nodebb.org/api/v1/plugins/' + PACKAGE,
                                          output / 'nodebb-imgur.json', host='packages.nodebb.org')
    pack, detail = json.loads(pack_bytes), json.loads(detail_bytes)
    latest = pack['dist-tags']['latest']
    if detail.get('code') != 'ok' or detail['payload']['name'] != PACKAGE or detail['payload']['latest'] != latest:
        raise ValueError('npm and NodeBB latest plugin versions disagree')
    if '1.0.16' not in detail['payload']['valid'] or latest not in detail['payload']['valid']:
        raise ValueError('NodeBB registry does not list both required versions')
    cli, toolchain = capture_npm(output)
    resolutions = []
    for version in dict.fromkeys(('1.0.16', latest)):
        print('Resolving ' + version, flush=True)
        resolutions.append(resolve_tree(cli, version, output))
    unique = {}
    for resolution in resolutions:
        for package in resolution['packages']:
            identity = (package['name'], package['version'])
            if identity in unique and any(unique[identity][key] != package[key] for key in ('resolved', 'integrity')):
                raise ValueError('resolution tarball pins disagree')
            unique[identity] = package
    verified = []
    for index, ((name, version), package) in enumerate(sorted(unique.items()), 1):
        print(f'Verifying {index}/{len(unique)} {name}@{version}', flush=True)
        identifier = hashlib.sha256((name + '@' + version).encode()).hexdigest()
        metadata_url = 'https://registry.npmjs.org/' + quote(name, safe='') + '/' + quote(version, safe='')
        content, record = download(metadata_url, metadata_directory / (identifier + '.json'), host='registry.npmjs.org')
        metadata = json.loads(content)
        if metadata['name'] != name or metadata['version'] != version:
            raise ValueError('registry package identity differs from resolution')
        if metadata['dist']['tarball'] != package['resolved'] or metadata['dist']['integrity'] != package['integrity']:
            raise ValueError('lockfile differs from published tarball pins')
        tarball, tar_record = download(package['resolved'], tarballs / (identifier + '.tgz'), host='registry.npmjs.org')
        verification = verify_tarball(tarball, metadata)
        verified.append(dict(name=name, version=version, dependencies=metadata.get('dependencies', {}),
                             optional_dependencies=metadata.get('optionalDependencies', {}),
                             peer_dependencies=metadata.get('peerDependencies', {}),
                             published_integrity=metadata['dist']['integrity'], published_sha1=metadata['dist']['shasum'],
                             metadata=record, tarball=tar_record, verification=verification))
    evidence = dict(condition='Imgur npm dependency and NodeBB registry assessment', toolchain=toolchain,
                    npm_packument=pack_record, nodebb_response=detail_record, latest=latest,
                    install_version='1.0.16', resolutions=resolutions, verified_packages=verified,
                    root_nodebb_transaction_verified=False, lifecycle_scripts_run=False,
                    cache_supplement_built=False, tests_run=False, baseline_ready=False)
    (output / 'assessment.json').write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(verified_packages=len(verified), latest=latest, toolchain=toolchain,
                         artifacts=str(output), cache_supplement_built=False), indent=2))


if __name__ == '__main__':
    main()
