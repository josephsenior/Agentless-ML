"""The candidate checkout, not the image's own copy, must be the code under test."""

import pytest

from agentless_ml.adapters.benchmarks.deepswe_execution import deepswe_test_command
from agentless_ml.validation import ReportFormat


def script(language, targets=()):
    command = deepswe_test_command(language, targets)
    return command.argv[2]


def test_python_puts_the_checkout_ahead_of_the_images_installed_package():
    # cattrs is installed editable from /app/src, so without this the container
    # imports /app/src/cattrs and every candidate patch is invisible.
    text = script("python")
    assert "PYTHONPATH=/tmp/work/src:/tmp/work" in text
    assert text.index("PYTHONPATH") < text.index("pytest")


def test_each_language_runs_inside_the_candidate_checkout():
    for language in ("go", "python", "javascript"):
        assert script(language).startswith("cd /tmp/work")


def test_reports_are_declared_where_the_runner_can_read_them():
    formats = {
        "go": ReportFormat.CTRF_JSON,
        "python": ReportFormat.JUNIT_XML,
        "javascript": ReportFormat.JUNIT_XML,
    }
    for language, expected in formats.items():
        report = deepswe_test_command(language).report
        assert report.format is expected
        assert report.path.startswith("/tmp/")


def test_go_result_is_go_tests_exit_status_not_the_reporters():
    # go-ctrf-json-reporter exits 1 whenever a test failed, after writing the
    # full report. Acting on that exit would turn every real regression into a
    # harness error; a missing report is caught by the runner instead.
    text = script("go")
    assert "rc=$?" in text and text.endswith("exit $rc")
    assert "||" not in text


def test_targets_are_arguments_not_text_spliced_into_the_script():
    command = deepswe_test_command("python", ("tests/test_any.py", "-k", "not slow"))
    assert command.argv[3] == "deepswe-tests"
    assert command.argv[4:] == ("tests/test_any.py", "-k", "not slow")
    assert "tests/test_any.py" not in command.argv[2]


def test_a_language_without_a_verified_command_is_refused():
    # Rust and TypeScript have no DeepSWE image checked here yet; guessing a
    # command would report results from a suite nobody has run.
    with pytest.raises(ValueError, match="no verified DeepSWE test command"):
        deepswe_test_command("rust")
