"""Acquire and verify a browser/dependency candidate. Never build or run tests."""

import hashlib
import json
import re
import shlex
import subprocess
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMAGE = "sha256:fce2e9ebe359b36b031e0b772159884795fc8383a047bc50eaa46c20fa06e4f6"
VERSION = "140.17.0esr"
BASE = f"https://archive.mozilla.org/pub/firefox/releases/{VERSION}/"
ARCHIVE = f"firefox-{VERSION}.tar.xz"
PRIMARY = "14F26682D0916CDD81E37B6D61B7B526D98F0353"
SUBKEY = "827E658608679618CD349F93678E455D76767AA3"
OUT = ROOT.parent / "output/deepswe-survey/testem-firefox-audit-2026-10-09"


def fetch(relative):
    path = OUT / Path(relative).name
    with urllib.request.urlopen(BASE + relative, timeout=60) as response:
        if not response.url.startswith(BASE):
            raise ValueError("Unexpected Mozilla redirect")
        with path.open("wb") as stream:
            while chunk := response.read(1024 * 1024):
                stream.write(chunk)
    return path


def matching_checksum(text, relative):
    matches = [line.split()[0] for line in text.splitlines()
               if len(line.split()) == 2 and line.split()[1].lstrip("*") == relative]
    if len(matches) != 1 or not re.fullmatch(r"[0-9a-f]{128}", matches[0]):
        raise ValueError("Missing or ambiguous Mozilla SHA512 entry")
    return matches[0]


def docker(script, *, network="none"):
    result = subprocess.run([
        "docker", "run", "--rm", "--pull=never", f"--network={network}",
        "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges",
        "--memory=8192m", "--memory-swap=8192m", "--cpus=2", "--pids-limit=2048",
        "--tmpfs", "/tmp:rw,exec,nosuid,nodev,size=4096m,mode=1777",
        "--mount", f"type=bind,source={OUT},target=/evidence",
        "--entrypoint", "/bin/sh", IMAGE, "-c", script,
    ], capture_output=True, text=True, timeout=900, check=False)
    if result.returncode:
        raise RuntimeError(f"Audit failed ({result.returncode}): {result.stdout}\n{result.stderr}")
    return {"stdout": result.stdout, "stderr": result.stderr}


ELF_AUDIT = r'''
import json,pathlib,re,subprocess
root=pathlib.Path('/tmp/firefox')
available=set(re.findall(r'^\s*(\S+)\s+\(',subprocess.check_output(['/sbin/ldconfig','-p'],text=True),re.M))
bundled={p.name for p in root.rglob('*') if p.is_file()}
bundled.update(p.name for p in pathlib.Path('/tmp/native-root').rglob('*') if p.is_file() or p.is_symlink())
records=[]
for p in root.rglob('*'):
    if not p.is_file(): continue
    with p.open('rb') as f: magic=f.read(4)
    if magic!=b'\x7fELF': continue
    r=subprocess.run(['readelf','-d',str(p)],capture_output=True,text=True,check=True)
    needed=re.findall(r'\(NEEDED\).*?\[(.*?)\]',r.stdout)
    records.append({'file':str(p.relative_to(root)),'needed':needed,
                    'missing':[n for n in needed if n not in available and n not in bundled]})
print(json.dumps(records,indent=2))
'''


APT_AUDIT = r'''
set -eu
mkdir -p /evidence/apt-lists/partial /evidence/debs/partial
opts='-o Dir::Etc::parts=- -o Dir::Etc::sourcelist=/evidence/sources.list -o Dir::Etc::sourceparts=- -o Dir::State::lists=/evidence/apt-lists -o Dir::Cache::archives=/evidence/debs -o APT::Sandbox::User=root'
apt-get $opts update
apt-get $opts --simulate --no-install-recommends install libgtk-3-0 libasound2 libdbus-glib-1-2 libx11-xcb1 libxt6
apt-get $opts --download-only --yes --no-install-recommends install libgtk-3-0 libasound2 libdbus-glib-1-2 libx11-xcb1 libxt6
'''


DEB_AUDIT = r'''
import hashlib,json,pathlib,subprocess
opts=['-o','Dir::Etc::parts=-','-o','Dir::Etc::sourcelist=/evidence/sources.list','-o','Dir::Etc::sourceparts=-','-o','Dir::State::lists=/evidence/apt-lists']
records=[]
for path in sorted(pathlib.Path('/evidence/debs').glob('*.deb')):
    name,version,arch=subprocess.check_output(['dpkg-deb','-f',str(path),'Package','Version','Architecture'],text=True).splitlines()
    # dpkg-deb labels multiple requested fields.
    name=name.removeprefix('Package: ');version=version.removeprefix('Version: ');arch=arch.removeprefix('Architecture: ')
    text=subprocess.check_output(['apt-cache',*opts,'show',f'{name}={version}'],text=True)
    paragraphs=[dict(line.split(': ',1) for line in block.splitlines() if ': ' in line and not line.startswith(' ')) for block in text.strip().split('\n\n')]
    actual=hashlib.sha256(path.read_bytes()).hexdigest()
    matches=[r for r in paragraphs if r.get('SHA256')==actual and int(r.get('Size','0'))==path.stat().st_size]
    if not matches: raise ValueError(f'No authenticated package hash match: {path}')
    records.append({'package':name,'version':version,'architecture':arch,'artifact':path.name,'bytes':path.stat().st_size,'sha256':actual,'repository_filename':matches[0]['Filename'],'depends':matches[0].get('Depends','')})
print(json.dumps(records,indent=2))
'''


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name in ("KEY", "SHA512SUMS", "SHA512SUMS.asc"):
        fetch(name)
    signature = docker("set -eu; mkdir -m 700 /tmp/gnupg; "
        "gpg --batch --homedir /tmp/gnupg --import /evidence/KEY; "
        "gpg --batch --homedir /tmp/gnupg --status-fd 1 --verify /evidence/SHA512SUMS.asc /evidence/SHA512SUMS")
    if not any(line.startswith(f"[GNUPG:] VALIDSIG {SUBKEY} ") and line.endswith(PRIMARY)
               for line in signature["stdout"].splitlines()):
        raise ValueError("Signature does not match independently pinned current Mozilla subkey")
    (OUT / "signature.json").write_text(json.dumps(signature, indent=2) + "\n")
    relative = f"linux-x86_64/en-US/{ARCHIVE}"
    expected = matching_checksum((OUT / "SHA512SUMS").read_text(), relative)
    archive = fetch(relative)
    if hashlib.sha512(archive.read_bytes()).hexdigest() != expected:
        raise ValueError("Firefox archive SHA512 mismatch")
    with tarfile.open(archive) as source:
        for member in source:
            if (member.name.startswith("/") or ".." in Path(member.name).parts
                    or member.isdev() or member.issym() or member.islnk()):
                raise ValueError("Archive contains an unsafe or unaudited member")
    print("Mozilla signature and Firefox SHA512 verified", flush=True)
    elf = docker(f"set -eu; tar -xJf /evidence/{ARCHIVE} --no-same-owner -C /tmp; "
                 "python3 -c " + shlex.quote(ELF_AUDIT))
    (OUT / "elf-before.json").write_text(elf["stdout"])
    (OUT / "sources.list").write_text(
        "deb [signed-by=/usr/share/keyrings/debian-archive-keyring.gpg] https://deb.debian.org/debian bookworm main\n"
        "deb [signed-by=/usr/share/keyrings/debian-archive-keyring.gpg] https://deb.debian.org/debian bookworm-updates main\n"
        "deb [signed-by=/usr/share/keyrings/debian-archive-keyring.gpg] https://deb.debian.org/debian-security bookworm-security main\n")
    print("Acquiring Debian signed metadata and download-only dependency closure; no installation", flush=True)
    apt = docker(APT_AUDIT, network="bridge")
    (OUT / "apt-acquisition.json").write_text(json.dumps(apt, indent=2) + "\n")
    debs = docker("python3 -c " + shlex.quote(DEB_AUDIT))
    packages = json.loads(debs["stdout"])
    manifest = {"label":"verified_browser_and_native_dependency_candidate_not_image_or_baseline",
        "task_id":"testem-per-launcher-reports", "image_id":IMAGE,
        "firefox_version":VERSION,"archive_url":BASE+relative,"archive_bytes":archive.stat().st_size,
        "archive_sha512":expected,"archive_sha256":hashlib.sha256(archive.read_bytes()).hexdigest(),
        "mozilla_primary_fingerprint":PRIMARY,"mozilla_signing_subkey_fingerprint":SUBKEY,
        "signature_verified":True,"packages":packages,
        "elf_missing_before":sorted({n for r in json.loads(elf['stdout']) for n in r['missing']}),
        "image_built":False,"browser_executed":False,"tests_run":False,
        "runtime_compatibility_verified":False,"official_survey_updated":False}
    (OUT / "verification.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print(json.dumps({'firefox_version':VERSION,'packages_verified':len(packages),
                      'verification_manifest':str(OUT/'verification.json')},indent=2),flush=True)


def verify_local_closure():
    """Inspect verified package payloads offline; no install scripts or browser execution."""
    path = OUT / "verification.json"
    manifest = json.loads(path.read_text())
    if not manifest['signature_verified'] or manifest['image_id'] != IMAGE:
        raise ValueError("Unexpected audit manifest")
    if hashlib.sha512((OUT / ARCHIVE).read_bytes()).hexdigest() != manifest['archive_sha512']:
        raise ValueError("Firefox artifact changed")
    for package in manifest['packages']:
        data = (OUT / 'debs' / package['artifact']).read_bytes()
        if hashlib.sha256(data).hexdigest() != package['sha256'] or len(data) != package['bytes']:
            raise ValueError("Debian artifact changed")
    closure = docker(f"set -eu; tar -xJf /evidence/{ARCHIVE} --no-same-owner -C /tmp; "
        "mkdir /tmp/native-root; for f in /evidence/debs/*.deb; do dpkg-deb -x \"$f\" /tmp/native-root; done; "
        "python3 -c " + shlex.quote(ELF_AUDIT))
    records = json.loads(closure['stdout'])
    manifest['elf_missing_after_package_payloads'] = sorted({n for r in records for n in r['missing']})
    manifest['package_payloads_inspected_offline'] = True
    signature = docker("set -eu; sha256sum /usr/share/keyrings/debian-archive-keyring.gpg; "
        "for f in /evidence/apt-lists/*InRelease; do "
        "gpgv --status-fd 1 --keyring /usr/share/keyrings/debian-archive-keyring.gpg \"$f\"; done")
    (OUT / 'debian-signatures.json').write_text(json.dumps(signature,indent=2)+'\n')
    manifest['debian_inrelease_signatures_verified_offline'] = True
    manifest['metadata_artifacts'] = [{'artifact':str(p.relative_to(OUT)).replace('\\','/'),
        'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size}
        for p in sorted((OUT/'apt-lists').glob('*')) if p.is_file() and p.name != 'lock']
    (OUT / 'elf-after.json').write_text(closure['stdout'])
    path.write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'packages':len(manifest['packages']),
        'elf_missing_after_package_payloads':manifest['elf_missing_after_package_payloads']},indent=2))


if __name__ == "__main__":
    main()
    verify_local_closure()
