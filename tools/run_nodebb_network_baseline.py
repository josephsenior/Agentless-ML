"""Network-enabled, unchanged-base NodeBB diagnostic; never candidate selection.

Uses the original pinned image and live public registries, not a cache supplement
or snapshot service. Normal Docker bridge egress is NOT a hostname allowlist.
"""
import argparse
from dataclasses import asdict, replace
import json
from pathlib import Path
import tempfile

from agentless_ml.validation import PublicTestCommand
from agentless_ml.workspace import LocalGitWorkspaceProvider, verify_sealed_repository
from check_v2_nodebb_setup import ROOT, SPEC
from v2_nodebb_public import NodeBBPublicSuiteRunner
from v2_nodebb_public import public_command


def baseline_command():
    command = public_command(1800)
    script = command.argv[2].replace('npm_config_offline=true', 'npm_config_offline=false')
    return replace(command, argv=(*command.argv[:2], 'export CI=true; ' + script,
                                  *command.argv[3:]))


def probe_command():
    # Fixed reviewed code, no candidate imports, credentials or dependency installs.
    script = r"""
const https=require('https'),fs=require('fs');
const urls=[
 'https://registry.npmjs.org/nodebb-plugin-imgur',
 'https://packages.nodebb.org/api/v1/plugins/nodebb-plugin-imgur'
];
const results=[];
(async()=>{
 for(const url of urls){
  const row=await new Promise((resolve,reject)=>{
   const req=https.get(url,{headers:{accept:'application/json'}},res=>{
    const chunks=[];let bytes=0;
    res.on('data',chunk=>{bytes+=chunk.length;if(bytes>1024*1024){res.destroy(Error('response too large'));return;}chunks.push(chunk);});
    res.on('error',reject);
    res.on('end',()=>{
     try{
      if(res.statusCode!==200)throw Error('HTTP '+res.statusCode);
      const body=JSON.parse(Buffer.concat(chunks).toString());
      const data=body.payload||body;
      if(data.name!=='nodebb-plugin-imgur')throw Error('unexpected package');
      resolve({url,status:res.statusCode,bytes,latest:data.latest||(data['dist-tags']||{}).latest});
     }catch(e){reject(e);}
    });
   });
   req.setTimeout(15000,()=>req.destroy(Error('request timeout')));
   req.on('error',reject);
  });
  results.push(row);
 }
 if(!results[0].latest||results[0].latest!==results[1].latest)throw Error('latest versions disagree');
 console.log(JSON.stringify({probe_complete:true,results}));
 fs.writeFileSync('/tmp/network-probe.json',JSON.stringify(results));
})().catch(e=>{console.error(e);process.exitCode=1;});
"""
    return PublicTestCommand(('node', '-e', script), timeout_seconds=60)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--probe-only', action='store_true')
    mode.add_argument('--full-suite', action='store_true')
    args = parser.parse_args()
    spec = json.loads(SPEC.read_bytes())
    repository = ROOT.parent / 'benchmarks/swe-bench-pro-v2/repos' / spec['instance_id']
    # Connected mode accepts only this sealed, unpatched public base.
    verify_sealed_repository(repository, spec['base_commit'])
    args.output.mkdir(parents=True, exist_ok=False)
    runner = NodeBBPublicSuiteRunner(spec['image_id'], args.output / 'executions',
                                    memory_mb=4096, cpus=1, tmpfs_mb=4096,
                                    pids_limit=2048, run_as_image_user=True,
                                    execution_phase='trusted-baseline', network_mode='bridge')
    with LocalGitWorkspaceProvider(repository, spec['base_commit'],
                                   Path(tempfile.gettempdir()) / 'agentless-v2-survey-workspaces').create() as workspace:
        execution = runner.run(workspace.path, probe_command() if args.probe_only else baseline_command())
        evidence = dict(condition='NodeBB live-network unchanged-base diagnostic',
                        task_id=spec['instance_id'], base_commit=spec['base_commit'],
                        image_id=runner.image_id, workspace=asdict(workspace.provenance),
                        execution=asdict(execution), network_mode='bridge',
                        execution_phase='trusted-baseline', hostname_allowlist=False,
                        completion_audit=runner.completion_audit,
                        tests_run=bool(args.full_suite), model_calls=0, verifier_run=False,
                        candidate_selection_eligible=False, cache_supplement_built=False)
    (args.output / 'result.json').write_text(json.dumps(evidence, indent=2, default=str) + '\n', encoding='utf-8')
    print(json.dumps(dict(status=execution.result.status.value, artifacts=execution.artifact_directory,
                         tests_run=evidence['tests_run'], network_mode='bridge'), indent=2))
    if execution.result.status.value not in ('pass', 'fail'):
        raise SystemExit('network diagnostic encountered an infrastructure error')
    if args.probe_only and execution.result.status.value != 'pass':
        raise SystemExit('network probe failed')


if __name__ == '__main__':
    main()
