import importlib.util
import sys
from pathlib import Path

from agentless_ml.adapters.benchmarks.deepswe_execution import MOCHA


def test_full_schedule_keeps_shared_command_and_both_public_globs():
    tools = Path(__file__).resolve().parents[1] / 'tools'
    sys.path.insert(0, str(tools))
    try:
        spec = importlib.util.spec_from_file_location('testem_baseline', tools / 'run_testem_firefox_baseline.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        command = module.selected_command()
        assert command == MOCHA.command(('tests/*_tests.js', 'tests/**/*_tests.js'), timeout_seconds=1800)
        assert command.timeout_seconds == 1800
        assert module.IMAGE == 'sha256:290cd40e1e05814859e3a0430b7bcbea77d92b8fcdd5161fd6ef1c1fc14e969d'
    finally:
        sys.path.pop(0)
