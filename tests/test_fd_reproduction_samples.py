"""Recorded Rust sample controls and saved-evidence audit; no Docker calls here."""

from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import runpy

import pytest

from agentless_ml.validation.reproduction import parse_reproduction_source, select_reproduction_source

ROOT = Path(__file__).resolve().parents[1]
TOOL = runpy.run_path(str(ROOT / 'tools/run_fd_path_sort_reproduction.py'))


def test_recorded_rust_sample_pool_contract():
    samples = TOOL['sample_responses']()
    assert len(samples) == 5
    with pytest.raises(ValueError):
        parse_reproduction_source(samples[0], 'rust')
    sources = {i: parse_reproduction_source(samples[i], 'rust') for i in range(1, 5)}
    assert '.arg("--version")' in sources[1] and '"--sort"' not in sources[1]
    assert '"--sort", "path"' in sources[2]
    assert sources[2] != sources[3] == sources[4]
    assert '0..1205' in sources[3] and 'Some(3)' in sources[3]
    assert select_reproduction_source({i: sources[i] for i in (2, 3, 4)}) == (3, 2)
    single = asdict(TOOL['responses'](with_public_regressions=True))
    pooled = asdict(TOOL['responses'](with_public_regressions=True, multiple_reproduction_samples=True))
    assert pooled.pop('reproduction_test') is None
    assert pooled.pop('reproduction_samples') == samples
    single.pop('reproduction_test')
    single.pop('reproduction_samples')
    assert single == pooled


@pytest.mark.parametrize('mutation', [None, 'wrong-winner', 'wrong-votes', 'passing-eligible',
                                      'wrong-source', 'wrong-status', 'late-selection', 'parsed-error-executed',
                                      'selection-checkpoint', 'missing-candidate'])
def test_sample_audit_checks_eligibility_votes_frozen_source_and_order(tmp_path, mutation):
    # These are synthetic saved records, not a successful fd execution.
    directory = tmp_path / 'run'
    directory.mkdir()
    samples = TOOL['sample_responses']()
    statuses = ['parse_error', 'pass', 'fail', 'fail', 'fail']

    def write(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding='utf-8')

    sources = {}
    for index in range(1, 5):
        source = parse_reproduction_source(samples[index], 'rust')
        sources[index] = source
        sample_dir = directory / 'reproduction-samples' / str(index)
        write(sample_dir / 'source.json', {'source': source,
              'source_sha256': hashlib.sha256(source.encode()).hexdigest()})
        write(sample_dir / 'baseline.json', {
            'checked_result': {'status': statuses[index], 'kind': 'reproduction'},
            'artifact_directory': str(sample_dir / 'reproduction-baseline/execution'),
        })
    selected_source = sources[3] if mutation != 'wrong-source' else sources[2]
    digest = hashlib.sha256(selected_source.encode()).hexdigest()
    selection = {'selected_sample_index': 2 if mutation == 'wrong-winner' else 3,
                 'vote_count': 1 if mutation == 'wrong-votes' else 2,
                 'eligible_sample_indices': [1, 2, 3, 4] if mutation == 'passing-eligible' else [2, 3, 4],
                 'voting_key': 'exact-source-v1', 'source_sha256': digest}
    if mutation == 'wrong-status':
        statuses[2] = 'pass'
    write(directory / 'reproduction-attempts.json', [
        {'sample_index': i, 'status': status} for i, status in enumerate(statuses)])
    selection_path = directory / 'reproduction-selection.json'
    write(selection_path, selection)
    # Deliberate fixture timestamps test ordering without wall-clock sleeps.
    selected_at = 1893456000 if mutation == 'late-selection' else 946684800
    os.utime(selection_path, (selected_at, selected_at))
    write(directory / 'reproduction-source.json', {'source': selected_source, 'source_sha256': digest})
    if mutation not in {'selection-checkpoint', 'missing-candidate'}:
        write(directory / 'executions/repair-1/execution/candidate.json', {
            'workspace': {'created_at': '2001-01-01T00:00:00+00:00'}})
    if mutation == 'parsed-error-executed':
        (directory / 'reproduction-samples/0/reproduction-baseline').mkdir(parents=True)
    if mutation and mutation != 'selection-checkpoint':
        with pytest.raises(AssertionError):
            TOOL['audit_sample_pool'](directory)
    else:
        summary, baseline, reports = TOOL['audit_sample_pool'](
            directory, require_candidate_validation=mutation != 'selection-checkpoint')
        assert summary['selected_sample_index'] == 3 and summary['vote_count'] == 2
        assert summary['selection_before_candidate_validation'] == (None if mutation == 'selection-checkpoint' else True)
        assert summary['candidate_validation_observed'] == (mutation != 'selection-checkpoint')
        assert baseline['checked_result']['status'] == 'fail'
        assert list(reports.values()) == ['passed', 'failed', 'failed', 'failed']
