"""Opt-in public Testem execution in the labelled offline-asset condition."""

import argparse
import json
import tempfile
from collections import Counter
from dataclasses import replace
from pathlib import Path

from agentless_ml.validation import DockerTestRunner
from agentless_ml.workspace import LocalGitWorkspaceProvider, verify_sealed_repository
from build_testem_qunit_image import RESULTS
from diagnose_testem_firefox import diagnostic_command, TEST
from run_kgateway_compile_diagnostic import keep_host_awake
from run_testem_firefox_baseline import ROOT, BASE, TASK
from run_testem_firefox_baseline import selected_command as full_public_command

IMAGE = 'sha256:96b08a03e607416b109f7d86186d1cdfe92755483eada98693e67ff5f2feba00'
PRIOR_SINGLE = ROOT / 'experiments/deepswe/testem_qunit_public_test_2026_10_09.json'
SUPERVISOR = r'''
import hashlib,http.client,json,os,pathlib,runpy,signal,subprocess,sys,time
module=runpy.run_path('/opt/testem-offline-qunit/offline-qunit.py')
service=None;test=None;rc=125
log=pathlib.Path('/tmp/offline-qunit-public-test.log')
output=log.open('w')
try:
 module['load_assets']()
 service=subprocess.Popen(['python3','/opt/testem-offline-qunit/offline-qunit.py'],stdout=output,stderr=subprocess.STDOUT)
 deadline=time.monotonic()+5
 while True:
  if service.poll() is not None:raise RuntimeError('Offline service exited during startup')
  try:
   connection=http.client.HTTPConnection('code.jquery.com',80,timeout=.5)
   connection.request('GET','/qunit/qunit-1.20.0.js');response=connection.getresponse();response.read();connection.close()
   if response.status!=200:raise RuntimeError('Offline service readiness request failed')
   break
  except OSError:
   if time.monotonic()>=deadline:raise RuntimeError('Offline service startup deadline')
   time.sleep(.1)
 checks=[]
 for route,(_,size,digest,mime) in module['PINS'].items():
  connection=http.client.HTTPConnection('code.jquery.com',80,timeout=3)
  connection.request('GET',route);response=connection.getresponse();data=response.read();connection.close()
  actual=hashlib.sha256(data).hexdigest()
  if response.status!=200 or len(data)!=size or actual!=digest or response.getheader('Content-Type')!=mime:
   raise RuntimeError('Offline service response does not match pinned asset')
  checks.append({'path':route,'sha256':actual,'bytes':len(data)})
 print(json.dumps({'event':'offline_asset_preflight_passed','assets':checks}),flush=True)
 test=subprocess.Popen(PUBLIC_TEST_ARGV,start_new_session=True)
 while test.poll() is None:
  if service.poll() is not None:raise RuntimeError('Offline service died during public test')
  time.sleep(.1)
 rc=test.returncode
except Exception as error:
 print(json.dumps({'event':'offline_asset_harness_error','message':str(error)}),flush=True)
 rc=125
finally:
 if test is not None and test.poll() is None:
  os.killpg(test.pid,signal.SIGTERM)
  try:test.wait(timeout=3)
  except subprocess.TimeoutExpired:os.killpg(test.pid,signal.SIGKILL);test.wait(timeout=3)
 if service is not None:
  service.terminate()
  try:service.wait(timeout=3)
  except subprocess.TimeoutExpired:service.kill();service.wait(timeout=3)
 output.close()
 print(json.dumps({'event':'offline_asset_service_log','text':log.read_text()}),flush=True)
sys.exit(rc if rc>=0 else 125)
'''


def selected_command(full=False):
    if full:
        command = full_public_command()
        # The full schedule uses the shared Mocha command, without a test filter
        # or diagnostic prototype wrappers. Only the proven HOME setting changes.
        command = replace(command, argv=(command.argv[0], command.argv[1],
            'mkdir -p /tmp/testem-firefox-home && export HOME=/tmp/testem-firefox-home && ' + command.argv[2],
            *command.argv[3:]))
    else:
        command = diagnostic_command('home-only')
    script = SUPERVISOR.replace('PUBLIC_TEST_ARGV', repr(list(command.argv)))
    return replace(command, argv=('python3', '-c', script))


class OfflineAssetRunner(DockerTestRunner):
    def __init__(self, *args, **kwargs):
        self.observed_host_config = None
        super().__init__(*args, **kwargs)

    def _docker(self, *args, **kwargs):
        if args and args[0] == 'create':
            args = (args[0], '--add-host=code.jquery.com:127.0.0.1', *args[1:])
        result = DockerTestRunner._docker(*args, **kwargs)
        if args and args[0] == 'inspect':
            self.observed_host_config = json.loads(result.stdout)[0]['HostConfig']
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--full', action='store_true', help='Run both unchanged public globs, without a grep filter')
    options = parser.parse_args()
    build = json.loads((RESULTS / 'build.json').read_text())
    preflight = json.loads((RESULTS / 'preflight.json').read_text())
    if (build['image_id'] != IMAGE or preflight['image_id'] != IMAGE
            or preflight.get('host_exit_code') != 0
            or not preflight.get('preflight', {}).get('all_checks_passed')):
        raise ValueError('Requires the exact built image and successful delivery preflight')
    if options.full:
        prior = json.loads(PRIOR_SINGLE.read_text())['result']
        if prior['image_id'] != IMAGE or prior['status'] != 'pass':
            raise ValueError('Requires the successful single public test in this exact image')
    repository = ROOT.parent / 'benchmarks/deepswe/repos' / TASK
    verify_sealed_repository(repository, BASE)
    provider = LocalGitWorkspaceProvider(repository, BASE,
        Path(tempfile.gettempdir()) / 'agentless-ml-survey-workspaces')
    runner = OfflineAssetRunner(IMAGE, RESULTS / 'public-test-logs', memory_mb=8192,
        cpus=2, tmpfs_mb=4096, pids_limit=2048, run_as_image_user=True)
    with keep_host_awake(True), provider.create() as workspace:
        execution = runner.run(workspace.path, selected_command(options.full))
    host = runner.observed_host_config
    evidence = {'condition': 'modified environment: offline public-asset delivery',
        'image_id': IMAGE, 'base_commit': BASE, 'public_test_filter': None if options.full else TEST,
        'status': execution.result.status.value, 'exit_code': execution.result.exit_code,
        'duration_seconds': execution.result.duration_seconds,
        'counts': dict(Counter(case.status.value for case in execution.result.test_cases)),
        'report_cases': len(execution.result.test_cases),
        'message': execution.message, 'artifacts': str(execution.artifact_directory),
        'docker_protections': {key: host[key] for key in ('NetworkMode', 'ReadonlyRootfs',
            'CapDrop', 'SecurityOpt', 'Memory', 'MemorySwap', 'NanoCpus', 'PidsLimit',
            'Tmpfs', 'Privileged', 'ExtraHosts', 'PortBindings')} if host else None,
        'environment_overrides': {'HOME': '/tmp/testem-firefox-home'},
        'public_test_source_modified': False, 'browser_arguments_modified': False,
        'full_suite_run': options.full, 'official_survey_updated': False,
        'diagnostic_prototype_observer': not options.full}
    if not options.full:
        evidence['cases'] = [{'id': case.test_id, 'status': case.status.value} for case in execution.result.test_cases]
    filename = 'offline-full-schedule.json' if options.full else 'offline-public-test.json'
    (Path(execution.artifact_directory) / filename).write_text(json.dumps(evidence, indent=2) + '\n')
    print(json.dumps(evidence, indent=2), flush=True)


if __name__ == '__main__':
    main()
