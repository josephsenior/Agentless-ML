"""Export guards for the fd public-suite diagnostic; no Docker execution here."""

import hashlib
import json
from pathlib import Path
import runpy

import pytest

from agentless_ml.repair import build_unified_diff

ROOT = Path(__file__).resolve().parents[1]
TOOL = runpy.run_path(str(ROOT / 'tools/run_fd_exported_regression.py'))


@pytest.mark.parametrize('mutation', [None, 'task', 'selection', 'patch', 'missing-newline'])
def test_export_is_exact_and_matches_saved_selection(tmp_path, mutation):
    patch = build_unified_diff({'src/walk.rs': 'old\n'}, {'src/walk.rs': 'new\n'})
    if mutation == 'missing-newline':
        patch = patch.rstrip('\n')
    record = {'instance_id': 'fd-deterministic-multi-key-sorting',
              'selected_candidate_id': 'repair-1', 'model_patch': patch}
    evidence = {'task_id': record['instance_id'], 'selected_candidate_id': 'repair-1',
                'final_patch_sha256': hashlib.sha256(patch.encode()).hexdigest()}
    if mutation == 'task':
        record['instance_id'] = 'another-task'
    elif mutation == 'selection':
        record['selected_candidate_id'] = 'repair-2'
    elif mutation == 'patch':
        record['model_patch'] = patch.replace('+new', '+different')
    prediction = tmp_path / 'prediction.json'
    prediction.write_text(json.dumps(record), encoding='utf-8')
    if mutation:
        with pytest.raises(ValueError):
            TOOL['load_export'](prediction, evidence)
    else:
        candidate = TOOL['load_export'](prediction, evidence)
        assert candidate.diff == patch
        assert candidate.diff_sha256 == evidence['final_patch_sha256']
        assert candidate.candidate_id == 'repair-1'
