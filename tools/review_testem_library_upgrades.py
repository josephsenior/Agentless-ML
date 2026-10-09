"""Offline package-plan review only: no downloads, installs, images or tests."""

import json
import re
import shlex
from verify_testem_firefox import OUT, docker

REVIEW = r'''
import gzip,hashlib,json,pathlib,subprocess
opts=['-o','Dir::Etc::parts=-','-o','Dir::Etc::sourcelist=/evidence/sources.list','-o','Dir::Etc::sourceparts=-','-o','Dir::State::lists=/evidence/apt-lists','-o','Dir::Cache::pkgcache=','-o','Dir::Cache::srcpkgcache=']
top=['libgtk-3-0','libasound2','libdbus-glib-1-2','libx11-xcb1','libxt6']
preserve=['libudev1=252.39-1~deb12u1','libsystemd0=252.39-1~deb12u1']
plans={}
for label,extra in [('original',[]),('preserve_versions',preserve),('preserve_versions_with_dbus_x11',preserve+['dbus-x11'])]:
    command=['apt-get',*opts,'--simulate','--no-install-recommends','install',*top,*extra]
    result=subprocess.run(command,capture_output=True,text=True)
    plans[label]={'argv':command,'exit_code':result.returncode,'stdout':result.stdout,'stderr':result.stderr}
installed=subprocess.run(['dpkg-query','-W','libudev1','libsystemd0','systemd','systemd-sysv','dbus','dbus-x11'],capture_output=True,text=True)
records={}
manifest=json.loads(pathlib.Path('/evidence/verification.json').read_text())
for name in ('libudev1','libsystemd0'):
    package=next(p for p in manifest['packages'] if p['package']==name)
    archive=pathlib.Path('/evidence/debs')/package['artifact']
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=package['sha256']: raise ValueError('Changed package')
    target=pathlib.Path('/tmp/review')/name
    target.mkdir(parents=True)
    subprocess.run(['dpkg-deb','-x',str(archive),str(target)],check=True)
    changelogs=list(target.rglob('changelog.Debian.gz'))
    records[name]={'candidate_version':package['version'],'changelog_head':gzip.decompress(changelogs[0].read_bytes()).decode()[:14000] if changelogs else None,
        'contents':subprocess.check_output(['dpkg-deb','-c',str(archive)],text=True)}
    control=target/'control'
    subprocess.run(['dpkg-deb','-e',str(archive),str(control)],check=True)
    records[name]['maintainer_scripts']={p.name:p.read_text(errors='replace') for p in control.iterdir() if p.name in ('preinst','postinst','prerm','postrm','triggers')}
status=pathlib.Path('/var/lib/dpkg/status').read_bytes()
print(json.dumps({'installed':installed.stdout,'package_database_sha256':hashlib.sha256(status).hexdigest(),'plans':plans,'upgrade_packages':records},indent=2))
'''


def main():
    result = docker('python3 -c ' + shlex.quote(REVIEW))
    evidence = json.loads(result['stdout'])
    evidence.update(label='offline_upgrade_review_not_build', downloads=False,
                    packages_installed=False, image_built=False, tests_run=False)
    target = OUT / 'upgrade-review.json'
    target.write_text(json.dumps(evidence, indent=2) + '\n')
    print(json.dumps({name:plan['exit_code'] for name,plan in evidence['plans'].items()},indent=2))
    print(target)


def selected_packages(stdout):
    return dict(re.findall(r'^Inst (\S+) (?:\[[^\]]+\] )?\((\S+)', stdout, re.M))


def summarize():
    evidence = json.loads((OUT/'upgrade-review.json').read_text())
    manifest = json.loads((OUT/'verification.json').read_text())
    plan = evidence['plans']['preserve_versions_with_dbus_x11']
    if plan['exit_code'] != 0 or '0 upgraded, 71 newly installed, 0 to remove' not in plan['stdout']:
        raise ValueError('Unexpected preserved-version plan')
    selected = selected_packages(plan['stdout'])
    original = selected_packages(evidence['plans']['original']['stdout'])
    metadata = docker("apt-cache -o Dir::Etc::parts=- "
        "-o Dir::Etc::sourcelist=/evidence/sources.list -o Dir::Etc::sourceparts=- "
        "-o Dir::State::lists=/evidence/apt-lists -o Dir::Cache::pkgcache= "
        "-o Dir::Cache::srcpkgcache= show dbus-x11=1.14.10-1~deb12u1")
    paragraphs=[dict(line.split(': ',1) for line in block.splitlines() if ': ' in line and not line.startswith(' '))
                for block in metadata['stdout'].strip().split('\n\n')]
    dbus=next(r for r in paragraphs if r.get('Architecture')=='amd64' and r.get('SHA256'))
    verified = {p['package']:p for p in manifest['packages']}
    packages=[]
    for name,version in selected.items():
        if name == 'dbus-x11':
            packages.append({'package':name,'version':version,'architecture':'amd64',
                'repository_filename':dbus['Filename'],'sha256':dbus['SHA256'],'bytes':int(dbus['Size']),
                'depends':dbus.get('Depends',''),'provides':dbus.get('Provides',''),
                'artifact_downloaded_and_verified':False})
        else:
            entry=verified[name].copy()
            if entry['version'] != version: raise ValueError('Changed package version')
            entry['artifact_downloaded_and_verified']=True
            packages.append(entry)
    summary={'label':'reviewed_no_upgrade_candidate_not_build',
        'task_id':manifest['task_id'],'image_id':manifest['image_id'],
        'preserved_versions':{'libudev1':'252.39-1~deb12u1','libsystemd0':'252.39-1~deb12u1'},
        'new_packages':len(selected),'upgrades':0,'removals':0,
        'removed_from_previous_plan':sorted(original.keys()-selected.keys()),
        'new_to_plan':sorted(selected.keys()-original.keys()),'packages':packages,
        'verified_downloads_reused':70,'pending_download_and_checksum_verification':['dbus-x11'],
        'browser_runtime_verified':False,'image_built':False,'tests_run':False,
        'official_survey_updated':False}
    (OUT/'upgrade-review-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k!='packages'},indent=2))


if __name__ == '__main__':
    main()
    summarize()
