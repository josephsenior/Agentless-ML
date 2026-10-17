import importlib
from pathlib import Path

from agentless_ml.validation import PublicTestCommand


def test_connected_baseline_preserves_test_command_and_removes_only_offline_setting(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'tools'))
    module = importlib.import_module('run_nodebb_network_baseline')
    offline = module.public_command(1800)
    online = module.baseline_command()
    assert online.argv[2] == 'export CI=true; ' + offline.argv[2].replace(
        'npm_config_offline=true', 'npm_config_offline=false')
    assert online.report == offline.report
    assert online.timeout_seconds == offline.timeout_seconds == 1800
    assert '8766' not in online.argv[2] and 'c.registry=' not in online.argv[2]


def test_connected_baseline_accepts_shared_factory_without_offline_keyword(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'tools'))
    module = importlib.import_module('run_nodebb_network_baseline')
    calls = []

    def public_command(timeout_seconds):
        calls.append(timeout_seconds)
        return PublicTestCommand(('sh', '-c', 'npm_config_offline=true npm test', 'sentinel'),
                                 timeout_seconds=timeout_seconds, failure_exit_codes=(1, 2))

    monkeypatch.setattr(module, 'public_command', public_command)
    command = module.baseline_command()
    assert calls == [1800]
    assert command.argv == ('sh', '-c', 'export CI=true; npm_config_offline=false npm test',
                            'sentinel')
    assert command.failure_exit_codes == (1, 2)


def test_probe_has_fixed_public_targets_and_no_package_install(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'tools'))
    module = importlib.import_module('run_nodebb_network_baseline')
    command = module.probe_command()
    assert command.timeout_seconds == 60
    assert command.argv[:2] == ('node', '-e')
    assert 'https://registry.npmjs.org/nodebb-plugin-imgur' in command.argv[2]
    assert 'https://packages.nodebb.org/api/v1/plugins/nodebb-plugin-imgur' in command.argv[2]
    assert 'npm install' not in command.argv[2] and 'require(\'nodebb-plugin' not in command.argv[2]
