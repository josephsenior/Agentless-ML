import importlib.util
import sys
from pathlib import Path


def test_observer_command_preserves_public_browser_test_and_report():
    tools = Path(__file__).resolve().parents[1] / 'tools'
    sys.path.insert(0, str(tools))
    try:
        spec = importlib.util.spec_from_file_location('testem_diagnostic', tools / 'diagnose_testem_firefox.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        command = module.diagnostic_command()
        assert command.argv[-3:] == ('tests/ci/ci_tests.js', '--grep', module.TEST)
        assert command.timeout_seconds == 1800
        assert command.report.path == '/tmp/report.xml'
        assert '--require /tmp/firefox-observer.cjs' in command.argv[2]
        assert 'exit "$rc"' in command.argv[2]
        assert 'MOZ_DISABLE' not in command.argv[2]
        cache = module.diagnostic_command('cache-only')
        assert cache.argv[3:] == command.argv[3:]
        assert cache.report == command.report
        assert cache.timeout_seconds == command.timeout_seconds
        assert cache.argv[2].endswith(command.argv[2])
        prefix = cache.argv[2][:-len(command.argv[2])]
        assert 'export XDG_CACHE_HOME=/tmp/testem-firefox-cache' in prefix
        assert 'export HOME=' not in prefix
        assert 'XDG_CONFIG_HOME=' not in prefix
        home = module.diagnostic_command('home-only')
        assert home.argv[3:] == command.argv[3:]
        assert home.argv[2].endswith(command.argv[2])
        home_prefix = home.argv[2][:-len(command.argv[2])]
        assert 'export HOME=/tmp/testem-firefox-home' in home_prefix
        assert 'XDG_CACHE_HOME=' not in home_prefix
        assert 'XDG_CONFIG_HOME=' not in home_prefix
    finally:
        sys.path.pop(0)


def test_minimal_native_controls_change_one_path_each():
    tools = Path(__file__).resolve().parents[1] / 'tools'
    sys.path.insert(0, str(tools))
    try:
        spec = importlib.util.spec_from_file_location('testem_native_controls', tools / 'probe_testem_firefox_connection.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cases = module.control_cases(True)
        assert cases[0] == ('image-home', 'testem', {})
        assert [set(settings) for _, _, settings in cases[1:]] == [
            {'XDG_CACHE_HOME'}, {'XDG_CONFIG_HOME'}, {'HOME'}]
        assert all(order == 'testem' for _, order, _ in cases)
        compile(module.PROBE.replace('CONTROL_CASES', repr(cases)), '<probe>', 'exec')
    finally:
        sys.path.pop(0)
