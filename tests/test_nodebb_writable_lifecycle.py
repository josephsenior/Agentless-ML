import importlib
from pathlib import Path

import pytest


@pytest.fixture
def module(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'tools'))
    return importlib.import_module('run_nodebb_writable_lifecycle')


def test_command_only_changes_dependency_setup_network_setting_and_test_selection(module):
    original = module.public_command(1800)
    command = module.lifecycle_command()
    script = command.argv[2]
    assert module._NODE_MODULES not in script
    assert module.COPY in script and '--no-preserve=ownership' in script
    assert 'npm_config_offline=false' in script
    assert "test/plugins.js --grep '^Plugins install/activate/uninstall '" in script
    assert '--ignore-scripts' not in script
    assert command.report == original.report and command.timeout_seconds == 1800


def test_group_requires_exact_five_passing_cases_and_clean_run_end(module):
    entries = [dict(rawFullTitle=title) for title in sorted(module.EXPECTED)]
    audit = dict(hook_failures=[], run_ended=True, aborted=False)
    assert module.assess_group({'passes': entries}, audit)['passed']
    assert not module.assess_group({'passes': entries[:-1]}, audit)['passed']
    assert not module.assess_group({'passes': entries[:-1], 'pending': entries[-1:]}, audit)['passed']
    assert not module.assess_group({'passes': entries}, {**audit, 'aborted': True})['passed']
    assert not module.assess_group({'passes': entries}, {**audit, 'hook_failures': ['error']})['passed']


def test_full_suite_removes_only_the_group_filter(module):
    selected = module.lifecycle_command()
    full = module.lifecycle_command(full_suite=True)
    assert full.argv[2] == selected.argv[2].replace(
        " test/plugins.js --grep '^Plugins install/activate/uninstall '", '')
    assert full.report == selected.report
    assert full.timeout_seconds == selected.timeout_seconds == 1800
