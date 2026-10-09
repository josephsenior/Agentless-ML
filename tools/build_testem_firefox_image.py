"""Build the explicitly verified no-upgrade Firefox image, with no build network."""

import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from verify_testem_firefox import ARCHIVE, IMAGE as PARENT, OUT, ROOT
from verify_testem_no_upgrade import check_artifact, validate_selection

TAG = 'agentless-ml/testem-firefox:2026-10-09'
RESULTS = ROOT.parent/'output/deepswe-survey/testem-firefox'
MANIFEST = ROOT/'experiments/deepswe/testem_no_upgrade_verified_2026_10_09.json'


def verify_inventory(image):
    script="import json,subprocess; text=subprocess.check_output(['dpkg-query','-W','-f=${binary:Package}\\t${Version}\\t${db:Status-Status}\\n'],text=True); print(json.dumps({r.split('\\t')[0]:r.split('\\t')[1] for r in text.splitlines() if r.split('\\t')[2]=='installed'}))"
    def inventory(target):
        command=['docker','run','--rm','--pull=never','--network=none','--read-only',
            '--cap-drop=ALL','--security-opt=no-new-privileges','--memory=8192m',
            '--memory-swap=8192m','--cpus=2','--pids-limit=2048',
            '--tmpfs','/tmp:rw,exec,nosuid,nodev,size=4096m,mode=1777',
            '--entrypoint','python3',target,'-c',script]
        return json.loads(subprocess.check_output(command,text=True,timeout=60))
    before=inventory(PARENT);after=inventory(image)
    added={k:v for k,v in after.items() if k not in before}
    changed={k:{'before':v,'after':after.get(k)} for k,v in before.items() if after.get(k)!=v}
    manifest=json.loads(MANIFEST.read_text())
    expected={p['package']:p['version'] for p in manifest['packages']}
    actual={k.split(':')[0]:v for k,v in added.items()}
    if changed or actual!=expected: raise ValueError('Image package changes differ from manifest')
    record={'image_id':image,'parent_image_id':PARENT,'added_packages':added,
            'changed_or_removed_existing_packages':changed,'exact_manifest_match':True}
    (RESULTS/'inventory.json').write_text(json.dumps(record,indent=2)+'\n')
    print('Image inventory verified: exactly 71 added packages, no existing version changes',flush=True)
    return record


def stage(manifest, context):
    packages=validate_selection(manifest)
    if not manifest['static_coverage_passed'] or manifest['pending_download_and_checksum_verification']:
        raise ValueError('Requires completed static verification')
    seed=context/'seed'; (seed/'debs').mkdir(parents=True)
    for item in packages:
        if not item['artifact_downloaded_and_verified']:
            raise ValueError('Unverified selected archive')
        source=OUT/'debs'/item['artifact']
        check_artifact(source,item)
        shutil.copyfile(source,seed/'debs'/source.name)
    firefox=OUT/ARCHIVE
    if hashlib.sha512(firefox.read_bytes()).hexdigest()!=manifest['firefox_sha512']:
        raise ValueError('Firefox archive changed')
    shutil.copyfile(firefox,seed/ARCHIVE)
    shutil.copyfile(ROOT/'experiments/deepswe/testem/Dockerfile.firefox',context/'Dockerfile')


def main():
    manifest=json.loads(MANIFEST.read_text())
    parent=subprocess.check_output(['docker','image','inspect',PARENT,'--format','{{.Id}}'],text=True).strip()
    if parent!=PARENT: raise ValueError('Wrong parent image')
    if subprocess.run(['docker','image','inspect',TAG],capture_output=True).returncode==0:
        raise ValueError('Refusing to overwrite an existing supplemented-image tag')
    RESULTS.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='testem-verified-firefox-') as temporary:
        context=Path(temporary)
        stage(manifest,context)
        command=['docker','build','--pull=false','--network=none','-t',TAG,str(context)]
        result=subprocess.run(command,capture_output=True,text=True,check=False)
        (RESULTS/'build.stdout.log').write_text(result.stdout)
        (RESULTS/'build.stderr.log').write_text(result.stderr)
        if result.returncode: raise RuntimeError('Build failed; see retained build logs')
    image=subprocess.check_output(['docker','image','inspect',TAG,'--format','{{.Id}}'],text=True).strip()
    verify_inventory(image)
    record={'label':'separate_verified_firefox_no_upgrade_environment',
        'parent_image_id':PARENT,'image_id':image,'tag':TAG,
        'manifest_sha256':hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
        'selected_packages':71,'preserved_versions':manifest['preserved_versions'],
        'network_during_build':'none','services_denied_by_existing_policy_rc_d':True,
        'tests_run':False,'official_survey_updated':False}
    (RESULTS/'build.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record,indent=2),flush=True)


if __name__=='__main__':
    main()
