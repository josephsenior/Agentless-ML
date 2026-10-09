"""Verify the new DBus archive and selected payloads; never install or execute them."""

import hashlib
import json
import shlex
import urllib.request
from pathlib import Path, PurePosixPath

from verify_testem_firefox import ARCHIVE, IMAGE, OUT, ROOT, docker


def check_artifact(path, pin):
    data = path.read_bytes()
    if len(data) != pin['bytes'] or hashlib.sha256(data).hexdigest() != pin['sha256']:
        raise ValueError(f'Archive size/hash mismatch: {path.name}')


def validate_selection(candidate):
    packages = candidate['packages']
    names = [p['package'] for p in packages]
    if (candidate['image_id'] != IMAGE or len(names) != 71 or len(set(names)) != 71
            or candidate['upgrades'] != 0 or candidate['removals'] != 0
            or {'libsystemd0','libudev1','systemd','systemd-sysv','libpam-systemd'} & set(names)):
        raise ValueError('Unexpected selected package set')
    for p in packages:
        filename = p.get('artifact', PurePosixPath(p['repository_filename']).name)
        if Path(filename).name != filename or '/' in filename or '\\' in filename:
            raise ValueError('Unsafe artifact basename')
    return packages


class DebianRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        if not newurl.startswith('https://deb.debian.org/debian/'):
            raise ValueError('Unexpected Debian redirect')
        return super().redirect_request(request, fp, code, msg, headers, newurl)


INSPECT = r'''
import hashlib,json,pathlib,re,subprocess
evidence=pathlib.Path('/evidence')
selection=json.loads((evidence/'no-upgrade-selection.json').read_text())
native=pathlib.Path('/tmp/native-root');native.mkdir()
for p in selection['packages']:
    archive=evidence/'debs'/p['artifact']
    data=archive.read_bytes()
    if len(data)!=p['bytes'] or hashlib.sha256(data).hexdigest()!=p['sha256']: raise ValueError('Changed archive')
    actual=subprocess.check_output(['dpkg-deb','-f',str(archive),'Package','Version','Architecture'],text=True)
    expected=f"Package: {p['package']}\nVersion: {p['version']}\nArchitecture: {p['architecture']}\n"
    if actual!=expected: raise ValueError(f'Package identity mismatch: {p["package"]}')
    subprocess.run(['dpkg-deb','-x',str(archive),str(native)],check=True)
subprocess.run(['tar','-xJf',str(evidence/selection['firefox_artifact']),'--no-same-owner','-C','/tmp'],check=True)
providers={name:'image:'+path for name,path in re.findall(r'^\s*(\S+)\s+\([^\n]*\)\s+=>\s+(\S+)',subprocess.check_output(['/sbin/ldconfig','-p'],text=True),re.M)}
records=[]
for label,root in [('firefox',pathlib.Path('/tmp/firefox')),('selected_native_payloads',native)]:
    for path in sorted(root.rglob('*')):
        if not path.is_file() or path.is_symlink(): continue
        with path.open('rb') as stream: magic=stream.read(4)
        if magic!=b'\x7fELF': continue
        dynamic=subprocess.check_output(['readelf','-d',str(path)],text=True)
        sonames=re.findall(r'\(SONAME\).*?\[(.*?)\]',dynamic)
        for name in sonames+[path.name]: providers.setdefault(name,label+':'+str(path.relative_to(root)))
        records.append({'group':label,'file':str(path.relative_to(root)),
            'needed':re.findall(r'\(NEEDED\).*?\[(.*?)\]',dynamic)})
for r in records:
    r['providers']={n:providers.get(n) for n in r['needed']}
    r['missing']=[n for n in r['needed'] if n not in providers]
installed=subprocess.check_output(['dpkg-query','-W','libudev1','libsystemd0'],text=True)
before=json.loads((evidence/'upgrade-review.json').read_text())['package_database_sha256']
after=hashlib.sha256(pathlib.Path('/var/lib/dpkg/status').read_bytes()).hexdigest()
if before!=after: raise ValueError('Image package database changed')
print(json.dumps({'records':records,'missing':sorted({n for r in records for n in r['missing']}),
    'installed_preserved_libraries':installed,'image_package_database_sha256':after,
    'image_package_database_unchanged':True},indent=2))
'''


def main():
    candidate = json.loads((ROOT/'experiments/deepswe/testem_no_upgrade_candidate_2026_10_09.json').read_text())
    packages = validate_selection(candidate)
    old = json.loads((ROOT/'experiments/deepswe/testem_firefox_dependencies_2026_10_09.json').read_text())
    for item in old['metadata_artifacts']:
        check_artifact(OUT/item['artifact'], item)
    # Repeat the signed-index verification offline; do not refresh frozen metadata.
    signatures = docker('set -eu; for f in /evidence/apt-lists/*InRelease; do '
        'gpgv --status-fd 1 --keyring /usr/share/keyrings/debian-archive-keyring.gpg "$f"; done')
    dbus = next(p for p in packages if p['package']=='dbus-x11')
    relative = dbus['repository_filename']
    if not relative.startswith('pool/main/d/dbus/') or '..' in PurePosixPath(relative).parts:
        raise ValueError('Unexpected Debian archive path')
    url = 'https://deb.debian.org/debian/' + relative
    target = OUT/'debs'/PurePosixPath(relative).name
    with urllib.request.build_opener(DebianRedirect()).open(url, timeout=60) as response:
        data = response.read()
    if len(data) != dbus['bytes'] or hashlib.sha256(data).hexdigest() != dbus['sha256']:
        raise ValueError('Downloaded DBus archive does not match pinned package record')
    target.write_bytes(data)
    dbus['artifact'] = target.name
    dbus['artifact_downloaded_and_verified'] = True
    # Recheck the new pin against the same authenticated frozen package index.
    metadata = docker('apt-cache -o Dir::Etc::parts=- '
        '-o Dir::Etc::sourcelist=/evidence/sources.list -o Dir::Etc::sourceparts=- '
        '-o Dir::State::lists=/evidence/apt-lists -o Dir::Cache::pkgcache= '
        '-o Dir::Cache::srcpkgcache= show dbus-x11=1.14.10-1~deb12u1')
    records=[dict(line.split(': ',1) for line in block.splitlines() if ': ' in line and not line.startswith(' '))
             for block in metadata['stdout'].strip().split('\n\n')]
    if not any(r.get('SHA256')==dbus['sha256'] and r.get('Filename')==relative
               and r.get('Architecture')==dbus['architecture'] and int(r.get('Size','0'))==dbus['bytes'] for r in records):
        raise ValueError('DBus pin no longer matches frozen authenticated index')
    for p in packages:
        check_artifact(OUT/'debs'/p['artifact'], p)
    firefox=OUT/ARCHIVE
    if hashlib.sha512(firefox.read_bytes()).hexdigest()!=old['archive_sha512']:
        raise ValueError('Firefox archive changed')
    selection={'packages':packages,'firefox_artifact':ARCHIVE}
    (OUT/'no-upgrade-selection.json').write_text(json.dumps(selection,indent=2)+'\n')
    print('DBus and all 71 selected archives verified; inspecting payloads offline',flush=True)
    result = docker('python3 -c '+shlex.quote(INSPECT))
    coverage=json.loads(result['stdout'])
    (OUT/'no-upgrade-elf-coverage.json').write_text(json.dumps(coverage,indent=2)+'\n')
    report={**candidate,'label':'verified_no_upgrade_payload_set_not_image_or_baseline',
        'packages':packages,'verified_downloads_reused':70,'new_archives_verified':1,
        'pending_download_and_checksum_verification':[],
        'dbus_archive_url':url,'frozen_metadata_rehashed':True,
        'debian_inrelease_signatures_reverified':True,'image_package_database_unchanged':True,
        'static_elf_files_inspected':len(coverage['records']),
        'static_missing_library_names':coverage['missing'],
        'static_coverage_passed':not coverage['missing'],
        'firefox_sha512':old['archive_sha512'],'browser_runtime_verified':False,
        'package_maintainer_scripts_executed':False,'image_built':False,'tests_run':False}
    (OUT/'no-upgrade-verification.json').write_text(json.dumps(report,indent=2)+'\n')
    (OUT/'no-upgrade-debian-signatures.json').write_text(json.dumps(signatures,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('packages','removed_from_previous_plan')},indent=2))
    if coverage['missing']:
        raise RuntimeError('Static dependency coverage is incomplete')


if __name__ == '__main__':
    main()
