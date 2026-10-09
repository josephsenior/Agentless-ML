import importlib.util
import sys
import shutil
import subprocess
from pathlib import Path

import pytest


def test_observer_command_preserves_public_browser_test_and_report():
    tools = Path(__file__).resolve().parents[1] / 'tools'
    sys.path.insert(0, str(tools))
    try:
        spec = importlib.util.spec_from_file_location('testem_diagnostic', tools / 'diagnose_testem_firefox.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        command = module.diagnostic_command()
        assert command.argv[-3:] == ('tests/ci/ci_tests.js', '--grep', module.TEST)
        assert command.timeout_seconds == 1800
        assert command.report.path == '/tmp/report.xml'
        assert '--require /tmp/firefox-observer.cjs' in command.argv[2]
        assert 'exit "$rc"' in command.argv[2]
        assert 'MOZ_DISABLE' not in command.argv[2]
        cache = module.diagnostic_command('cache-only')
        assert cache.argv[3:] == command.argv[3:]
        assert cache.report == command.report
        assert cache.timeout_seconds == command.timeout_seconds
        assert cache.argv[2].endswith(command.argv[2])
        prefix = cache.argv[2][:-len(command.argv[2])]
        assert 'export XDG_CACHE_HOME=/tmp/testem-firefox-cache' in prefix
        assert 'export HOME=' not in prefix
        assert 'XDG_CONFIG_HOME=' not in prefix
        home = module.diagnostic_command('home-only')
        assert home.argv[3:] == command.argv[3:]
        assert home.argv[2].endswith(command.argv[2])
        home_prefix = home.argv[2][:-len(command.argv[2])]
        assert 'export HOME=/tmp/testem-firefox-home' in home_prefix
        assert 'XDG_CACHE_HOME=' not in home_prefix
        assert 'XDG_CONFIG_HOME=' not in home_prefix
    finally:
        sys.path.pop(0)


def test_minimal_native_controls_change_one_path_each():
    tools = Path(__file__).resolve().parents[1] / 'tools'
    sys.path.insert(0, str(tools))
    try:
        spec = importlib.util.spec_from_file_location('testem_native_controls', tools / 'probe_testem_firefox_connection.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cases = module.control_cases(True)
        assert cases[0] == ('image-home', 'testem', {})
        assert [set(settings) for _, _, settings in cases[1:]] == [
            {'XDG_CACHE_HOME'}, {'XDG_CONFIG_HOME'}, {'HOME'}]
        assert all(order == 'testem' for _, order, _ in cases)
        compile(module.PROBE.replace('CONTROL_CASES', repr(cases)), '<probe>', 'exec')
    finally:
        sys.path.pop(0)


def test_reporter_observer_preserves_inputs_counters_and_failure_decision():
    node = shutil.which('node')
    if node is None:
        pytest.skip('Node is required for the diagnostic observer contract check')
    observer = Path(__file__).resolve().parents[1] / 'tools/testem_firefox_observer.cjs'
    script = r'''
const assert = require('assert/strict');
const vm = require('vm');
const fs = require('fs');
const events = [];
const sentinel = {};
let seen;
class Reporter {
  constructor() { this.total=0; this.passed=0; this.skipped=0; this.todo=0; }
  report(name,result) { seen={receiver:this,name,result}; this.total++; if(result.passed)this.passed++; return sentinel; }
  hasPassed() { return this.total <= this.passed+this.skipped+this.todo; }
}
class Server { emit() { return 'unchanged'; } }
const modules = {
  fs: {appendFileSync(path,text) {events.push(JSON.parse(text));}},
  child_process: {spawn() { throw new Error('No child process should run in this unit check'); }},
  http: {Server},
  '/candidate/lib/utils/reporter': Reporter
};
vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),{
  require(name) {assert.ok(name in modules); return modules[name];},
  process:{cwd:()=>'/candidate',env:{HOME:'/tmp/home'},version:process.version}
});
const reporter=new Reporter();
const result={passed:false,name:'Global error: QUnit is not defined'};
assert.equal(reporter.report('Firefox',result),sentinel);
assert.equal(seen.receiver,reporter);
assert.equal(seen.name,'Firefox');
assert.equal(seen.result,result);
assert.equal(reporter.hasPassed(),false);
assert.equal(reporter.total,1);
assert.equal(reporter.passed,0);
assert.equal(result.passed,false);
assert.equal(events.find(e=>e.event==='reporter_result').result.name,result.name);
assert.equal(events.find(e=>e.event==='reporter_has_passed').returned,false);
'''
    completed = subprocess.run([node, '-e', script, str(observer)],
                               capture_output=True, text=True, timeout=15)
    assert completed.returncode == 0, completed.stderr
