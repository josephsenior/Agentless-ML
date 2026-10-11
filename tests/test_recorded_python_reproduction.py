"""Opt-in real-container verification of Python reporting and sample selection."""

import os
from dataclasses import replace
import json
from pathlib import Path
import runpy

import pytest

from agentless_ml.workflow.fixed import WorkflowError
from agentless_ml.validation import DockerTestRunner, python_reproduction_command
from agentless_ml.schemas import ValidationStatus


def load_tool():
    return runpy.run_path(str(Path(__file__).resolve().parents[1] / 'tools/run_recorded_python_reproduction.py'))


@pytest.mark.skipif(os.environ.get('AGENTLESS_PYTHON_REPRODUCTION_DOCKER_TESTS') != '1',
                    reason='opt-in Python Docker controller diagnostic')
@pytest.mark.parametrize('samples', [False, True])
def test_recorded_python_reproduction(tmp_path, samples):
    tool = load_tool()
    result = tool['run_slice'](tmp_path / 'python-controller', samples=samples)
    assert result['selected_candidate_id'] == 'repair-3'


@pytest.mark.skipif(os.environ.get('AGENTLESS_PYTHON_REPRODUCTION_DOCKER_TESTS') != '1',
                    reason='opt-in Python Docker sample error diagnostic')
def test_background_error_stops_sample_selection(tmp_path, monkeypatch):
    tool = load_tool()
    bundle = replace(tool['responses'](True), reproduction_samples=(
        '```python\nimport threading\ndef worker(): raise RuntimeError("setup")\n'
        't = threading.Thread(target=worker)\nt.start()\nt.join()\nassert False\n```',
    ))
    monkeypatch.setitem(tool['run_slice'].__globals__, 'responses', lambda samples: bundle)
    output = tmp_path / 'python-error'
    with pytest.raises(WorkflowError, match='infrastructure'):
        tool['run_slice'](output, samples=True)
    (directory,) = (output / 'runs').iterdir()
    attempts = json.loads((directory / 'reproduction-attempts.json').read_bytes())
    assert attempts == [{'sample_index': 0, 'status': 'harness_error'}]
    assert not (directory / 'reproduction-selection.json').exists()
    assert not (directory / 'executions').exists()
    assert not (directory / 'prediction.json').exists()
    assert not list((output / 'workspaces').iterdir())


@pytest.mark.skipif(os.environ.get('AGENTLESS_PYTHON_REPRODUCTION_DOCKER_TESTS') != '1',
                    reason='opt-in Python Docker background timeout diagnostic')
def test_nonterminating_daemon_is_timeout_not_pass(tmp_path):
    root = Path(__file__).resolve().parents[1]
    pin = json.loads((root / 'experiments/deepswe/corpus_pin.json').read_bytes())
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'reproduce.py').write_text(
        'import threading\nthreading.Thread(target=lambda: threading.Event().wait(), daemon=True).start()\n')
    runner = DockerTestRunner(pin['container_digests']['wasmi-trap-coredumps'], tmp_path / 'artifacts',
                              memory_mb=4096, tmpfs_mb=4096, cpus=1, pids_limit=2048, run_as_image_user=True)
    result = runner.run(source, python_reproduction_command('reproduce.py', timeout_seconds=2))
    assert result.result.status is ValidationStatus.TIMEOUT
