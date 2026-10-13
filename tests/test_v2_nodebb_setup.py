"""Public CI setup stays inside a disposable offline candidate workspace."""
import importlib
from pathlib import Path


def test_redis_setup_uses_public_inputs_and_distinct_databases(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'tools'))
    module = importlib.import_module('check_v2_nodebb_setup')
    command = module.setup_command()
    script = command.argv[2]
    assert command.timeout_seconds == 300
    assert 'cp install/package.json package.json' in script
    assert '--bind 127.0.0.1' in script
    assert '--dir /tmp' in script
    assert 'npm_config_offline=true' in script
    assert 'node app --setup=' in script
    assert 'npm test' not in script
    assert module.SETUP['redis:database'] == 0
    assert module.CI['database'] == 1
    assert command.report is None
