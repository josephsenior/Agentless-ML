"""Trace one unchanged public browser test; not a full baseline or a fix."""

import argparse
import json
import shlex
import tempfile
from dataclasses import replace
from pathlib import Path

from agentless_ml.adapters.benchmarks.deepswe_execution import MOCHA
from agentless_ml.validation import DockerTestRunner
from agentless_ml.workspace import LocalGitWorkspaceProvider, verify_sealed_repository
from run_testem_firefox_baseline import ROOT, RESULTS, TASK, BASE, IMAGE
from run_kgateway_compile_diagnostic import keep_host_awake

TEST = '^ci mode app multiple launchers returns successfully with passed and skipped tests$'
PATH_SETTINGS = {
    'cache-only': ('XDG_CACHE_HOME', '/tmp/testem-firefox-cache'),
    'config-only': ('XDG_CONFIG_HOME', '/tmp/testem-firefox-config'),
    'home-only': ('HOME', '/tmp/testem-firefox-home'),
}


def diagnostic_command(path_setting=None):
    observer = (ROOT / 'tools/testem_firefox_observer.cjs').read_text()
    write = 'from pathlib import Path; Path("/tmp/firefox-observer.cjs").write_text(' + repr(observer) + ')'
    command = MOCHA.command(('tests/ci/ci_tests.js', '--grep', TEST), timeout_seconds=1800)
    script = 'python3 -c ' + shlex.quote(write) + ' && ' + command.argv[2].replace(
        '/app/node_modules/.bin/mocha ',
        'node --require /tmp/firefox-observer.cjs /app/node_modules/mocha/bin/mocha.js ')
    script += '; rc=$?; cat /tmp/firefox-observer.jsonl; exit "$rc"'
    if path_setting is not None:
        key, directory = PATH_SETTINGS[path_setting]
        script = f'mkdir -p {shlex.quote(directory)} && export {key}={shlex.quote(directory)} && ' + script
    return replace(command, argv=(command.argv[0], command.argv[1], script, *command.argv[3:]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--path-setting', choices=tuple(PATH_SETTINGS),
                        help='Explicitly labelled single-variable environment control, not a shared fix')
    options = parser.parse_args()
    build = json.loads((RESULTS / 'build.json').read_text())
    if build['image_id'] != IMAGE:
        raise ValueError('Exact verified image required')
    repository = ROOT.parent / 'benchmarks/deepswe/repos' / TASK
    verify_sealed_repository(repository, BASE)
    provider = LocalGitWorkspaceProvider(repository, BASE,
        Path(tempfile.gettempdir()) / 'agentless-ml-survey-workspaces')
    runner = DockerTestRunner(IMAGE, RESULTS / 'diagnostics', memory_mb=8192,
        cpus=2, tmpfs_mb=4096, pids_limit=2048, run_as_image_user=True)
    with keep_host_awake(True), provider.create() as workspace:
        execution = runner.run(workspace.path, diagnostic_command(options.path_setting))
    evidence = {'label': 'targeted_public_test_with_launch_http_observer_not_full_baseline',
        'image_id': IMAGE, 'base_commit': BASE, 'public_test_filter': TEST,
        'status': execution.result.status.value, 'exit_code': execution.result.exit_code,
        'duration_seconds': execution.result.duration_seconds,
        'cases': [{'id': case.test_id, 'status': case.status.value} for case in execution.result.test_cases],
        'artifacts': str(execution.artifact_directory), 'official_survey_updated': False,
        'test_source_modified': False, 'browser_arguments_modified': False,
        'path_setting': options.path_setting,
        'environment_overrides': dict([PATH_SETTINGS[options.path_setting]]) if options.path_setting else {},
        'shared_benchmark_configuration_modified': False}
    (Path(execution.artifact_directory) / 'diagnostic.json').write_text(json.dumps(evidence, indent=2) + '\n')
    print(json.dumps(evidence, indent=2), flush=True)


if __name__ == '__main__':
    main()
