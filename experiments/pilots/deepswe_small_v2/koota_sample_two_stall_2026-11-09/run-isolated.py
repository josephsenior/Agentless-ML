import json, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / "src"))
from agentless_ml.adapters.benchmarks import DeepSWEDataset, DeepSWEDatasetPin, pinned_load_options
from agentless_ml.scoring import DeepSWEVerifier
from agentless_ml.scoring.deepswe import _inputs
root=Path(__file__).resolve().parent
pin=json.loads(Path("experiments/deepswe/corpus_pin.json").read_text())
(task,)=DeepSWEDataset(Path("../benchmarks/deepswe/corpus/tasks"),DeepSWEDatasetPin(pin["revision"],pin["agent_files_sha256"],pin["task_count"])).load_tasks(task_ids=("koota-composite-trait-aspects",),**pinned_load_options(pin))
v=DeepSWEVerifier(Path("../benchmarks/deepswe/corpus"),pin["revision"])
patch=Path("experiments/pilots/deepswe_small_v2/koota_sample_two_diagnostic_2026-11-08/sample-two.patch").read_bytes()
name="agentless-koota-stall-isolated-20261109"
script="""set -eu
cd /app
python3 /tests/grader.py prepare
cat > packages/core/diagnostic.config.ts <<'CONFIG'
import { defineConfig } from 'vitest/config';
export default defineConfig({ test: { setupFiles: ['./diagnostic.setup.ts'] } });
CONFIG
cat > packages/core/diagnostic.setup.ts <<'SETUP'
import { beforeEach, afterEach, expect } from 'vitest';
beforeEach(() => console.error('[diagnostic start]', expect.getState().currentTestName));
afterEach(() => console.error('[diagnostic end]', expect.getState().currentTestName));
SETUP
timeout --kill-after=5s 20s pnpm -F core test run tests/aspect.test.ts -t "should not match unchanged entities" --config diagnostic.config.ts --reporter=verbose
"""
def call(*args,**kw):
 return subprocess.run(['docker',*args],capture_output=True,timeout=kw.pop('timeout',60),**kw)
r=call('create','--name',name,'--network=none','--cpus=2','--memory=8192m','--memory-swap=8192m','--pids-limit=4096','--security-opt=no-new-privileges','--pull=never','--entrypoint','bash',task.container_digest,'-c',script)
if r.returncode: raise RuntimeError(r.stderr.decode())
try:
 r=call('cp','-',name+':/',input=_inputs(v.verifier_files(task),patch))
 if r.returncode: raise RuntimeError(r.stderr.decode())
 started=time.monotonic()
 r=call('start','--attach',name,timeout=110)
 (root/'isolated-output.txt').write_bytes(r.stdout+r.stderr)
 record={'scope':'Isolated unchanged-entity test, exact saved patch; diagnostic only','container':name,'exit_code':r.returncode,'elapsed_seconds':time.monotonic()-started,'model_calls':0,'limits':{'seconds':20,'cpus':2,'memory_gib':8,'network':'none'}}
 (root/'isolated.json').write_text(json.dumps(record,indent=2)+'\n')
 print(json.dumps(record))
 print((r.stdout+r.stderr).decode(errors='replace')[-4000:].encode('ascii',errors='backslashreplace').decode())
finally:
 call('rm','--force','--volumes',name)
