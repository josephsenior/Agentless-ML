"""One offline headless browser smoke check, not a public test baseline."""

import json
import base64
import hashlib
import subprocess
import uuid

from build_testem_firefox_image import RESULTS

STARTUP = r'''
import base64,hashlib,json,pathlib,struct,subprocess
root=pathlib.Path('/tmp/firefox-startup');root.mkdir()
home=root/'home';home.mkdir()
profile=root/'profile';profile.mkdir()
import os
env=os.environ.copy();env.update(HOME=str(home),XDG_CACHE_HOME=str(home/'cache'),XDG_CONFIG_HOME=str(home/'config'))
version=subprocess.run(['firefox','--version'],env=env,capture_output=True,text=True,timeout=30)
page=root/'startup.html'
page.write_text('<!doctype html><html><body style="background:white;color:navy;font:28px sans-serif"><h1>Firefox offline startup OK</h1><p id="js">Waiting for JavaScript</p><script>document.getElementById("js").textContent="JavaScript executed";</script></body></html>')
png=root/'startup.png'
command=['firefox','--headless','--no-remote','--profile',str(profile),'--window-size','640,480','--screenshot',str(png),page.as_uri()]
result=subprocess.run(command,env=env,capture_output=True,text=True,timeout=180)
data=png.read_bytes() if png.exists() else b''
dimensions=list(struct.unpack('>II',data[16:24])) if data.startswith(b'\x89PNG\r\n\x1a\n') else None
print(json.dumps({'label':'offline_headless_startup_not_public_tests','version_exit_code':version.returncode,
    'version_stdout':version.stdout,'version_stderr':version.stderr,
    'command':command,'exit_code':result.returncode,'stdout':result.stdout,'stderr':result.stderr,
    'png_bytes':len(data),'png_sha256':hashlib.sha256(data).hexdigest() if data else None,
    'png_base64':base64.b64encode(data).decode(),
    'png_dimensions':dimensions,'preserved_library_versions':subprocess.check_output(['dpkg-query','-W','libudev1','libsystemd0'],text=True),
    'browser_sandbox_disable_requested':False,'tests_run':False},indent=2))
raise SystemExit(0 if version.returncode==0 and result.returncode==0 and dimensions==[640,480] else 1)
'''


def docker_args(image,name):
    return ['docker','run','--name',name,'--pull=never','--network=none','--read-only',
        '--cap-drop=ALL','--security-opt=no-new-privileges','--memory=8192m','--memory-swap=8192m',
        '--cpus=2','--pids-limit=2048','--init',
        '--tmpfs','/tmp:rw,exec,nosuid,nodev,size=4096m,mode=1777',
        '--entrypoint','python3',image,'-c',STARTUP]


def main():
    build=json.loads((RESULTS/'build.json').read_text())
    image=build['image_id'];name='agentless-ml-testem-startup-'+uuid.uuid4().hex
    record={'label':'offline_headless_startup_not_public_tests','image_id':image,
        'container_name':name,'tests_run':False,'official_survey_updated':False}
    try:
        result=subprocess.run(docker_args(image,name),capture_output=True,text=True,timeout=240)
        (RESULTS/'startup.stderr.log').write_text(result.stderr)
        record.update(host_exit_code=result.returncode)
        if result.stdout.strip():
            browser=json.loads(result.stdout)
            png=base64.b64decode(browser.pop('png_base64'),validate=True)
            if len(png)!=browser['png_bytes'] or hashlib.sha256(png).hexdigest()!=browser['png_sha256']:
                raise ValueError('Screenshot capture hash mismatch')
            (RESULTS/'startup.png').write_bytes(png)
            record['browser']=browser
            record['screenshot_exported']=True
            (RESULTS/'startup.stdout.log').write_text(json.dumps(browser,indent=2)+'\n')
        inspect=json.loads(subprocess.check_output(['docker','inspect',name],text=True))[0]
        host=inspect['HostConfig']
        record['docker_protections']={k:host[k] for k in ('NetworkMode','ReadonlyRootfs','CapDrop','SecurityOpt','Memory','MemorySwap','NanoCpus','PidsLimit','Tmpfs','Privileged')}
        record['container_state']=inspect['State']
    except subprocess.TimeoutExpired:
        record['error']='bounded startup timeout'
    except (ValueError,subprocess.CalledProcessError,OSError) as error:
        record['error']=str(error)
    finally:
        cleanup=subprocess.run(['docker','rm','--force','--volumes',name],capture_output=True,text=True)
        record['owned_container_removed']=cleanup.returncode==0
        (RESULTS/'startup.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record,indent=2),flush=True)
    return 0 if record.get('host_exit_code')==0 and record.get('screenshot_exported') and not record.get('error') and record['owned_container_removed'] else 1


if __name__=='__main__':
    raise SystemExit(main())
