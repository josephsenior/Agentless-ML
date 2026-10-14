"""Full replay preserves the verified page setup and removes only file selection."""
import importlib
from pathlib import Path


def test_full_command_differs_only_by_api_file_selection(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'tools'))
    module = importlib.import_module('run_nodebb_registry_page')
    page = module.page_command()
    full = module.page_command(full_suite=True)
    assert page.argv[2].replace('output=/tmp/nodebb-report.json test/api.js;',
                              'output=/tmp/nodebb-report.json;') == full.argv[2]
    assert full.timeout_seconds == page.timeout_seconds == 1800
    assert full.report == page.report
    assert full.argv[2].startswith('export CI=true; ')
