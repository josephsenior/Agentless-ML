"""Protected native HTTP preflight only; never run public benchmark tests."""

import json
import subprocess
import uuid

from build_testem_qunit_image import RESULTS
from check_testem_firefox_startup import docker_args

PREFLIGHT = r'''
import hashlib,http.client,json,os,pathlib,runpy,socket,subprocess,time
module=runpy.run_path('/opt/testem-offline-qunit/offline-qunit.py')
module['load_assets']()
home=pathlib.Path('/tmp/testem-firefox-home');home.mkdir();os.environ['HOME']=str(home)
log=pathlib.Path('/tmp/offline-qunit.log');output=log.open('w')
process=subprocess.Popen(['python3','/opt/testem-offline-qunit/offline-qunit.py'],stdout=output,stderr=subprocess.STDOUT)
checks=[]
def request(host,path,method='GET'):
 connection=http.client.HTTPConnection('code.jquery.com',80,timeout=3)
 connection.request(method,path,headers={'Host':host})
 response=connection.getresponse();data=response.read();headers=dict(response.getheaders());status=response.status
 connection.close()
 return status,headers,data
try:
 deadline=time.monotonic()+5
 while True:
  if process.poll() is not None:raise RuntimeError('Offline asset service exited during startup')
  try:
   with socket.create_connection(('127.0.0.1',80),timeout=.2):break
  except OSError:
   if time.monotonic()>deadline:raise RuntimeError('Offline asset service startup timeout')
   time.sleep(.1)
 for route,(_,size,digest,mime) in module['PINS'].items():
  status,headers,data=request('code.jquery.com',route)
  actual=hashlib.sha256(data).hexdigest()
  ok=status==200 and len(data)==size and actual==digest and headers.get('X-Content-SHA256')==digest and headers.get('Content-Type')==mime
  checks.append({'case':'GET '+route,'passed':ok,'status':status,'bytes':len(data),'sha256':actual,'content_type':headers.get('Content-Type')})
  status,headers,data=request('code.jquery.com:80',route,'HEAD')
  checks.append({'case':'HEAD '+route,'passed':status==200 and not data and int(headers['Content-Length'])==size,'status':status,'body_bytes':len(data)})
 for host,path,method,expected in [('code.jquery.com','/missing','GET',404),('code.jquery.com','/favicon.ico','GET',404),('unexpected.invalid','/qunit/qunit-1.20.0.js','GET',404),('code.jquery.com','/qunit/qunit-1.20.0.js?extra=1','GET',404),('code.jquery.com','/qunit/qunit-1.20.0.js','POST',501)]:
  status,_,_=request(host,path,method)
  checks.append({'case':method+' '+host+path,'status':status,'passed':status==expected})
finally:
 process.terminate()
 try:process.wait(timeout=3)
 except subprocess.TimeoutExpired:process.kill();process.wait(timeout=3)
 output.close()
print(json.dumps({'condition':'modified environment: offline public-asset delivery','checks':checks,'service_log':log.read_text(),'all_checks_passed':all(c['passed'] for c in checks),'tests_run':False,'home':str(home)},indent=2))
raise SystemExit(0 if all(c['passed'] for c in checks) else 1)
'''


def main():
    build = json.loads((RESULTS / 'build.json').read_text())
    image = build['image_id']
    name = 'agentless-ml-testem-qunit-preflight-' + uuid.uuid4().hex
    command = docker_args(image, name)
    command[2:2] = ['--add-host=code.jquery.com:127.0.0.1']
    command[-1] = PREFLIGHT
    evidence = {'image_id': image, 'container_name': name,
                'official_survey_updated': False, 'benchmark_tests_run': False}
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=60)
        (RESULTS / 'preflight.stdout.log').write_text(result.stdout)
        (RESULTS / 'preflight.stderr.log').write_text(result.stderr)
        evidence.update(host_exit_code=result.returncode, stderr=result.stderr)
        if result.stdout.strip():
            evidence['preflight'] = json.loads(result.stdout)
        inspect = json.loads(subprocess.check_output(['docker', 'inspect', name], text=True))[0]
        evidence['docker_protections'] = {key: inspect['HostConfig'][key] for key in (
            'NetworkMode', 'ReadonlyRootfs', 'CapDrop', 'SecurityOpt', 'Memory', 'MemorySwap',
            'NanoCpus', 'PidsLimit', 'Tmpfs', 'Privileged', 'ExtraHosts', 'PortBindings')}
        evidence['state'] = inspect['State']
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, ValueError, OSError) as error:
        evidence['error'] = str(error)
    finally:
        removed = subprocess.run(['docker', 'rm', '--force', '--volumes', name], capture_output=True, text=True)
        evidence['owned_container_removed'] = removed.returncode == 0
        (RESULTS / 'preflight.json').write_text(json.dumps(evidence, indent=2) + '\n')
    print(json.dumps(evidence, indent=2))
    return 0 if evidence.get('host_exit_code') == 0 and evidence.get('preflight', {}).get('all_checks_passed') and evidence['owned_container_removed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
