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
    finally:
        sys.path.pop(0)
