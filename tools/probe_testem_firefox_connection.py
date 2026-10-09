"""Synthetic localhost controls, not benchmark tests or an environment fix."""

import argparse
import json
import subprocess
import uuid

from check_testem_firefox_startup import docker_args
from run_testem_firefox_baseline import IMAGE, RESULTS

PROBE = r'''
import http.server,json,os,pathlib,signal,subprocess,threading,time
requests=[]
class Handler(http.server.BaseHTTPRequestHandler):
 def do_GET(self):
  requests.append({'path':self.path,'user_agent':self.headers.get('User-Agent'),'time':time.time()})
  self.send_response(200);self.send_header('Content-Type','text/html');self.end_headers()
  self.wfile.write(b'<html><body>local diagnostic<script>fetch("/beacon")</script></body></html>' if self.path.startswith('/page') else b'ok')
 def log_message(self,*args): pass
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
threading.Thread(target=server.serve_forever,daemon=True).start()
results=[]
for label,order,settings in CONTROL_CASES:
 root=pathlib.Path('/tmp')/label;root.mkdir();profile=root/'profile';profile.mkdir()
 env=os.environ.copy()
 for key,relative in settings.items():
  directory=root/relative;directory.mkdir(parents=True,exist_ok=True);env[key]=str(directory)
 url='http://127.0.0.1:%s/page?case=%s'%(server.server_port,label)
 args=['firefox','-profile','--headless',str(profile),url] if order=='testem' else ['firefox','--headless','-profile',str(profile),url]
 out=open(root/'stdout','w');err=open(root/'stderr','w');start=len(requests)
 process=subprocess.Popen(args,env=env,stdout=out,stderr=err,start_new_session=True)
 deadline=time.monotonic()+15
 while time.monotonic()<deadline and process.poll() is None and not any(r['path']=='/beacon' for r in requests[start:]):time.sleep(.1)
 observed=requests[start:];natural_exit=process.poll()
 try:os.killpg(process.pid,signal.SIGTERM)
 except ProcessLookupError:pass
 try:process.wait(timeout=3)
 except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=3)
 out.close();err.close()
 results.append({'case':label,'args':args,'home':env.get('HOME'),'path_overrides':{key:env[key] for key in settings},'path_environment':{key:env.get(key) for key in ('HOME','XDG_CACHE_HOME','XDG_CONFIG_HOME')},'requests':observed,'javascript_beacon':any(r['path']=='/beacon' for r in observed),'natural_exit_code':natural_exit,'stdout':(root/'stdout').read_text(),'stderr':(root/'stderr').read_text()})
server.shutdown()
print(json.dumps({'label':'synthetic_loopback_argument_home_controls_not_benchmark','cases':results,'tests_run':False},indent=2))
'''


def control_cases(minimal=False):
    if minimal:
        return [('image-home', 'testem', {}),
                ('cache-only', 'testem', {'XDG_CACHE_HOME': 'cache'}),
                ('config-only', 'testem', {'XDG_CONFIG_HOME': 'config'}),
                ('home-only', 'testem', {'HOME': 'home'})]
    writable = {'HOME': 'home', 'XDG_CACHE_HOME': 'home/cache', 'XDG_CONFIG_HOME': 'home/config'}
    return [(order + ('-writable-home' if enabled else '-image-home'), order,
             writable if enabled else {})
            for order, enabled in [('testem', False), ('conventional', False),
                                   ('testem', True), ('conventional', True)]]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--minimal', action='store_true', help='Isolate HOME and each XDG path separately')
    options = parser.parse_args()
    name = 'agentless-ml-testem-controls-' + uuid.uuid4().hex
    args = docker_args(IMAGE, name)
    cases = control_cases(options.minimal)
    args[-1] = PROBE.replace('CONTROL_CASES', repr(cases))
    record = {'image_id': IMAGE, 'container_name': name, 'official_survey_updated': False,
              'minimal_path_controls': options.minimal}
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=120)
        record.update(host_exit_code=result.returncode, host_stderr=result.stderr)
        if result.stdout.strip():
            record['probe'] = json.loads(result.stdout)
        inspect = json.loads(subprocess.check_output(['docker', 'inspect', name], text=True))[0]
        record['protections'] = {key: inspect['HostConfig'][key] for key in (
            'NetworkMode', 'ReadonlyRootfs', 'CapDrop', 'SecurityOpt', 'Memory',
            'MemorySwap', 'NanoCpus', 'PidsLimit', 'Tmpfs', 'Privileged')}
        record['state'] = inspect['State']
    finally:
        cleanup = subprocess.run(['docker', 'rm', '--force', '--volumes', name], capture_output=True, text=True)
        record['owned_container_removed'] = cleanup.returncode == 0
        target = RESULTS / (name + '.json')
        target.write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record, indent=2), flush=True)


if __name__ == '__main__':
    main()
