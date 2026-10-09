"""Synthetic localhost controls, not benchmark tests or an environment fix."""

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
for order,writable in [('testem',False),('conventional',False),('testem',True),('conventional',True)]:
 label=order+('-writable-home' if writable else '-image-home')
 root=pathlib.Path('/tmp')/label;root.mkdir();profile=root/'profile';profile.mkdir()
 env=os.environ.copy()
 if writable:
  home=root/'home';home.mkdir();env.update(HOME=str(home),XDG_CACHE_HOME=str(home/'cache'),XDG_CONFIG_HOME=str(home/'config'))
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
 results.append({'case':label,'args':args,'home':env.get('HOME'),'requests':observed,'javascript_beacon':any(r['path']=='/beacon' for r in observed),'natural_exit_code':natural_exit,'stdout':(root/'stdout').read_text(),'stderr':(root/'stderr').read_text()})
server.shutdown()
print(json.dumps({'label':'synthetic_loopback_argument_home_controls_not_benchmark','cases':results,'tests_run':False},indent=2))
'''


def main():
    name = 'agentless-ml-testem-controls-' + uuid.uuid4().hex
    args = docker_args(IMAGE, name)
    args[-1] = PROBE
    record = {'image_id': IMAGE, 'container_name': name, 'official_survey_updated': False}
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
