"""Run Testem's full public Mocha schedule in the verified Firefox image."""

import json
import tempfile
from collections import Counter
from pathlib import Path

from agentless_ml.adapters.benchmarks.deepswe_execution import MOCHA
from agentless_ml.validation import DockerTestRunner
from agentless_ml.workspace import LocalGitWorkspaceProvider, verify_sealed_repository
from run_kgateway_compile_diagnostic import keep_host_awake

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT.parent / 'output/deepswe-survey/testem-firefox'
TASK = 'testem-per-launcher-reports'
BASE = '158f61ea91c9613d2011c41ee9be40ada1d7a307'
IMAGE = 'sha256:290cd40e1e05814859e3a0430b7bcbea77d92b8fcdd5161fd6ef1c1fc14e969d'


def selected_command():
    # Both globs are present in the pinned package.json. Keep the shared runner
    # and its report capture unchanged; no browser flags or test exclusions.
    return MOCHA.command(('tests/*_tests.js', 'tests/**/*_tests.js'), timeout_seconds=1800)


def main():
    build = json.loads((RESULTS / 'build.json').read_text())
    startup = json.loads((RESULTS / 'startup.json').read_text())
    if build['image_id'] != IMAGE or startup['image_id'] != IMAGE:
        raise ValueError('Build and startup must identify this exact image')
    if (startup.get('host_exit_code') != 0 or startup.get('error')
            or not startup.get('screenshot_exported')
            or startup['browser']['exit_code'] != 0):
        raise ValueError('A successful protected offline startup is required')
    repository = ROOT.parent / 'benchmarks/deepswe/repos' / TASK
    verify_sealed_repository(repository, BASE)
    provider = LocalGitWorkspaceProvider(repository, BASE,
        Path(tempfile.gettempdir()) / 'agentless-ml-survey-workspaces')
    runner = DockerTestRunner(IMAGE, RESULTS / 'logs', memory_mb=8192,
        cpus=2, tmpfs_mb=4096, pids_limit=2048, run_as_image_user=True)
    command = selected_command()
    print('Starting one full public schedule, offline, capped at 1800 seconds', flush=True)
    # This scoped Windows request changes no persistent power settings.
    with keep_host_awake(True), provider.create() as workspace:
        execution = runner.run(workspace.path, command)
    evidence = {
        'label': 'full_public_schedule_separate_verified_firefox_environment',
        'task_id': TASK, 'base_commit': BASE, 'image_id': runner.image_id,
        'command': list(command.argv), 'timeout_seconds': command.timeout_seconds,
        'status': execution.result.status.value, 'exit_code': execution.result.exit_code,
        'duration_seconds': execution.result.duration_seconds,
        'counts': dict(Counter(case.status.value for case in execution.result.test_cases)),
        'report_cases': len(execution.result.test_cases), 'message': execution.message,
        'artifacts': str(execution.artifact_directory), 'official_survey_updated': False,
    }
    (Path(execution.artifact_directory) / 'public-schedule.json').write_text(
        json.dumps(evidence, indent=2) + '\n')
    print(json.dumps(evidence, indent=2), flush=True)
    return 0 if execution.result.exit_code == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
