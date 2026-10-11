"""Trusted standalone Node and Go reproduction reporters; not sandboxes."""

import re
from pathlib import PurePosixPath

from agentless_ml.schemas import ValidationKind

from .docker import PublicTestCommand
from .reports import ReportFormat, TestReport
from .reproduction import ReproductionSpec


_NODE_RUNNER = r"""
const fs = require('fs');
const path = require('path');
const Module = require('module');
const { AssertionError } = require('assert');
const [source, report, language] = process.argv.slice(1);
const exit = process.exit.bind(process);
let finished = false;
function write(status) {
  fs.writeFileSync(report, JSON.stringify({results: {tests: [
    {suite: 'generated-reproduction', name: 'standalone', status}
  ]}}));
}
function fail(error) {
  if (finished) return;
  finished = true;
  console.error(error);
  const assertion = error instanceof AssertionError;
  write(assertion ? 'failed' : 'other');
  exit(assertion ? 1 : 2);
}
process.on('uncaughtException', fail);
process.on('unhandledRejection', fail);
process.on('exit', () => { if (!finished) write('other'); });
process.on('beforeExit', () => {
  if (finished) return;
  finished = true;
  const clean = !process.exitCode || Number(process.exitCode) === 0;
  write(clean ? 'passed' : 'other');
  process.exitCode = clean ? 0 : 2;
});
try {
  const filename = path.resolve(source);
  if (language === 'typescript' && /\.ts$/.test(filename)) {
    const ts = require('typescript');
    const compiled = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
      fileName: filename, reportDiagnostics: true,
      compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020}
    });
    const errors = (compiled.diagnostics || []).filter(d => d.category === ts.DiagnosticCategory.Error);
    if (errors.length) throw new SyntaxError(ts.formatDiagnosticsWithColorAndContext(errors, {
      getCanonicalFileName: p => p, getCurrentDirectory: () => process.cwd(), getNewLine: () => '\n'
    }));
    const mod = new Module(filename, module);
    mod.filename = filename;
    mod.paths = Module._nodeModulePaths(path.dirname(filename));
    mod._compile(compiled.outputText, filename);
  } else {
    require(filename);
  }
} catch (error) { fail(error); }
"""


def _node_command(path: str, language: str, timeout_seconds: float, node_path: str | None):
    argv = ("node", "--unhandled-rejections=strict", "-e", _NODE_RUNNER,
            path, "/tmp/reproduction.json", language)
    if node_path is not None:
        if not node_path or any(c in node_path for c in "\0\r\n"):
            raise ValueError("NODE_PATH must be a nonempty runtime search path")
        argv = ("env", "NODE_PATH=" + node_path, *argv)
    command = PublicTestCommand(
        argv, kind=ValidationKind.REPRODUCTION, timeout_seconds=timeout_seconds,
        failure_exit_codes=(1, 2),
        report=TestReport(ReportFormat.CTRF_JSON, "/tmp/reproduction.json"),
    )
    ReproductionSpec(path, command)
    return command


def javascript_reproduction_command(
    path: str, *, timeout_seconds: float = 60, node_path: str | None = None,
) -> PublicTestCommand:
    """CommonJS script; uncaught Node AssertionError alone means test failure."""
    if PurePosixPath(path).suffix not in {".js", ".cjs"}:
        raise ValueError("JavaScript reproduction requires a .js or .cjs file")
    return _node_command(path, "javascript", timeout_seconds, node_path)


def typescript_reproduction_command(
    path: str, *, timeout_seconds: float = 60, node_path: str | None = None,
) -> PublicTestCommand:
    """Transpile a .ts entry point, or run an existing CommonJS TS-loader script.

    Transpilation checks syntax, not types. Imported TS modules need the repo's
    own loader; this adapter does not install a global require hook.
    """
    if PurePosixPath(path).suffix not in {".ts", ".cjs"}:
        raise ValueError("TypeScript reproduction requires a .ts or .cjs file")
    return _node_command(path, "typescript", timeout_seconds, node_path)


_GO_RUNNER = r"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

package, test, report = sys.argv[1:]
os.environ['GOPROXY'] = 'off'
os.environ['GOSUMDB'] = 'off'
os.environ['GOCACHE'] = '/tmp/go-build'
cases = []
code = 2
events = ''
try:
    with tempfile.TemporaryDirectory(prefix='reproduction-go-') as directory:
        binary = str(Path(directory) / ('test.exe' if os.name == 'nt' else 'test'))
        build = subprocess.run(['go', 'test', '-c', '-o', binary, package])
        if build.returncode:
            raise RuntimeError('Go reproduction did not compile')
        run = subprocess.run([binary, '-test.v=test2json', '-test.run=^' + test + '$',
                              '-test.count=1'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        sys.stdout.buffer.write(run.stdout)
        sys.stdout.buffer.flush()
        converted = subprocess.run(['go', 'tool', 'test2json', '-p', package],
                                   input=run.stdout, stdout=subprocess.PIPE, check=True)
        events = converted.stdout.decode('utf-8')
        active = set()
        for line in converted.stdout.splitlines():
            event = json.loads(line)
            name, action = event.get('Test'), event.get('Action')
            if not name:
                continue
            if action == 'run':
                active.add(name)
            if action in ('pass', 'fail', 'skip'):
                if name not in active:
                    raise RuntimeError('Go report has an unmatched terminal event')
                active.remove(name)
                cases.append({'suite': package, 'name': name,
                              'status': {'pass': 'passed', 'fail': 'failed', 'skip': 'skipped'}[action]})
        failed = any(c['status'] == 'failed' for c in cases)
        if (active or not any(c['name'] == test for c in cases)
                or run.returncode not in (0, 1)
                or (run.returncode == 1) != failed):
            raise RuntimeError('Go reproduction has incomplete or abnormal test evidence')
        code = run.returncode
except Exception as error:
    print(error, file=sys.stderr)
    cases.append({'suite': package, 'name': '__adapter_error__', 'status': 'other'})
Path(report).write_text(json.dumps({'results': {'tests': cases}, 'go_events_jsonl': events}), encoding='utf-8')
sys.exit(code)
"""


def go_reproduction_command(
    path: str, *, test_name: str, timeout_seconds: float = 600,
) -> PublicTestCommand:
    """Compile the containing package, run one named test, retain all its subtests.

    Requires python3 and Go in the image. A panic/abnormal binary exit is an
    error, not a testing.T failure. Build and execution share the outer timeout.
    """
    if not path.endswith("_test.go") or not re.fullmatch(r"Test[A-Z0-9_][A-Za-z0-9_]*", test_name):
        raise ValueError("Go reproduction requires a _test.go file and a literal Test name")
    package = "./" + str(PurePosixPath(path).parent)
    command = PublicTestCommand(
        ("python3", "-c", _GO_RUNNER, package, test_name, "/tmp/reproduction.json"),
        kind=ValidationKind.REPRODUCTION, timeout_seconds=timeout_seconds,
        failure_exit_codes=(1, 2),
        report=TestReport(ReportFormat.CTRF_JSON, "/tmp/reproduction.json"),
    )
    ReproductionSpec(path, command)
    return command
