"""Recorded Python Docker checks, including background errors and sample voting."""

from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import hashlib
import json
import os
from pathlib import Path
import subprocess

from agentless_ml.schemas import Benchmark, TaskSpec, ValidationKind
from agentless_ml.validation import DockerTestRunner, RegressionTest, ReproductionSpec, python_reproduction_command
from agentless_ml.workflow import FixedWorkflowController, RecordedStageResponses

ROOT = Path(__file__).resolve().parents[1]
SOURCE = 'def add(a, b):\n    return a - b\n'
REPRODUCTION = '```python\nfrom calculator import add\nassert add(2, 3) == 5\n```'
BACKGROUND_REPAIR = '''def add(a, b):
    if a:
        import threading
        import time
        def worker():
            time.sleep(.05)
            raise RuntimeError("background setup failed")
        threading.Thread(target=worker, daemon=True).start()
    return a + b
'''
FILES = {
    'calculator.py': SOURCE,
    'public_check.py': 'from calculator import add\nassert add(0, 0) == 0\n',
}


def git(directory: Path, *args: str) -> str:
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith('GIT_')}
    env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull)
    return subprocess.run([
        'git', '-c', 'safe.directory=' + str(directory), '-c', 'user.name=Python Fixture',
        '-c', 'user.email=fixture@example.invalid', '-c', 'core.autocrlf=false',
        '-c', 'core.hooksPath=' + os.devnull, *args,
    ], cwd=directory, env=env, check=True, capture_output=True, text=True).stdout.strip()


def responses(samples: bool) -> RecordedStageResponses:
    def repair(content: str) -> str:
        return '```python\n### calculator.py\n<<<<<<< SEARCH\n' + SOURCE + '=======\n' + content + '>>>>>>> REPLACE\n```'

    bundle = RecordedStageResponses(
        file_localization='```\ncalculator.py\n```',
        symbol_localization='```\ncalculator.py\nfunction: add\n```',
        edit_localization='```\ncalculator.py\nline: 1\nline: 2\n```',
        repairs=('malformed', repair(BACKGROUND_REPAIR),
                 repair(SOURCE.replace('a - b', 'a * b')), repair(SOURCE.replace('a - b', 'a + b'))),
        regression_exclusions='', reproduction_test=REPRODUCTION,
        source='authored controlled Python fixture; no model or benchmark answers',
    )
    if samples:
        bundle = replace(bundle, reproduction_test=None, reproduction_samples=(
            'malformed', '```python\nassert True\n```', REPRODUCTION,
            '```python\nfrom calculator import add\nassert add(3, 2) == 5\n```', REPRODUCTION,
        ))
    return bundle


def run_slice(output: Path, *, samples: bool = False) -> dict:
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    source = output / 'source'
    source.mkdir()
    for name, content in FILES.items():
        (source / name).write_bytes(content.encode())
    git(source, 'init')
    git(source, 'add', '.')
    git(source, 'commit', '-m', 'authored Python reproduction fixture')
    pin = json.loads((ROOT / 'experiments/deepswe/corpus_pin.json').read_bytes())
    # Reuse a local pinned image with Python; this does not run the Wasmi task.
    image = pin['container_digests']['wasmi-trap-coredumps']
    runner = DockerTestRunner(image, output / 'executions', memory_mb=4096,
                              cpus=1, tmpfs_mb=4096, pids_limit=2048, run_as_image_user=True)
    task = TaskSpec(
        benchmark=Benchmark.CONTROLLED_FIXTURE, benchmark_revision='python-reproduction-v2',
        instance_id='controlled__python_reproduction_samples' if samples else 'controlled__python_reproduction',
        language='python', repository_url='https://example.invalid/authored-python',
        base_commit=git(source, 'rev-parse', 'HEAD'),
        problem_statement='add must return the sum; add(2, 3) must equal 5.',
        container_image=image, container_digest=image, memory_megabytes=4096,
    )
    revision = git(ROOT, 'rev-parse', 'HEAD')
    if git(ROOT, 'status', '--porcelain', '--untracked-files=all'):
        revision += '+dirty'
    result = FixedWorkflowController(
        task=task, source_repository=source, workspace_root=output / 'workspaces',
        artifact_root=output / 'runs', runner=runner, public_commands=(),
        regression_tests=(RegressionTest('existing-zero', replace(
            python_reproduction_command('public_check.py'), kind=ValidationKind.REGRESSION)),),
        reproduction_spec=ReproductionSpec('reproduce.py', python_reproduction_command('reproduce.py')),
        implementation_revision=revision, harness_revision='python-reproduction-v2',
        model_name='recorded/manual-python-reproduction',
    ).run(responses(samples))
    directory = Path(result.artifact_directory)
    assert [a.status for a in result.attempts] == ['repair_error', 'validated', 'validated', 'validated']
    candidates = [a.candidate for a in result.attempts if a.candidate]
    outcomes = [[v.status.value for v in c.validation] for c in candidates]
    assert outcomes == [['pass', 'harness_error'], ['pass', 'fail'], ['pass', 'pass']]
    selection = None
    if samples:
        selection = json.loads((directory / 'reproduction-selection.json').read_bytes())
        assert selection['selected_sample_index'] == 2 and selection['vote_count'] == 2
        assert selection['eligible_sample_indices'] == [2, 3, 4]
        attempts = json.loads((directory / 'reproduction-attempts.json').read_bytes())
        assert [a['status'] for a in attempts] == ['parse_error', 'pass', 'fail', 'fail', 'fail']
        frozen = json.loads((directory / 'reproduction-source.json').read_bytes())
        assert frozen['source'] == 'from calculator import add\nassert add(2, 3) == 5\n'
        assert frozen['source_sha256'] == selection['source_sha256']
    else:
        baseline = json.loads((directory / 'reproduction-baseline.json').read_bytes())
        assert baseline['checked_result']['status'] == 'fail'
    public = json.loads((directory / 'regression-baseline.json').read_bytes())
    assert public[0]['result']['status'] == 'pass'
    reports = list(directory.rglob('report.json'))
    assert len(reports) == (11 if samples else 8)
    background_reports = [json.loads(p.read_bytes()) for p in (directory / 'executions/repair-1').rglob('report.json')]
    assert any(r['background_errors'] == ['thread'] for r in background_reports)
    prediction = json.loads((directory / 'prediction.json').read_bytes())
    assert prediction == asdict(result.prediction)
    assert prediction['selected_candidate_id'] == 'repair-3' and result.run.model_calls == 0
    patch = prediction['model_patch']
    assert 'a + b' in patch and 'reproduce.py' not in patch and 'public_check.py' not in patch
    assert hashlib.sha256(patch.encode()).hexdigest() == result.run.final_patch_sha256
    assert not git(source, 'status', '--porcelain', '--untracked-files=all')
    assert all((source / name).read_bytes() == content.encode() for name, content in FILES.items())
    assert not list((output / 'workspaces').iterdir())
    summary = {
        'scope': 'authored Python Docker controller fixture, not a benchmark result',
        'artifact_directory': str(directory), 'sample_pool': samples,
        'candidate_outcomes': outcomes, 'selected_candidate_id': prediction['selected_candidate_id'],
        'sample_selection': selection, 'retained_reports': len(reports),
        'container_digest': runner.image_id, 'implementation_revision': revision,
        'model_calls': 0, 'wall_time_seconds': result.run.wall_time_seconds,
        'final_patch_sha256': result.run.final_patch_sha256,
        'source_unchanged': True, 'candidate_workspaces_cleaned': True,
    }
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--samples', action='store_true')
    args = parser.parse_args()
    print(json.dumps(run_slice(args.output, samples=args.samples), indent=2))
