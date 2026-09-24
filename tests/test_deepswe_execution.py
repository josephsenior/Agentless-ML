"""The candidate checkout, not the image's own copy, must be the code under test."""

import json

import pytest

from agentless_ml.adapters.benchmarks.deepswe_execution import (
    TEST_COMMANDS,
    deepswe_test_command,
    deepswe_test_runner,
)
from agentless_ml.validation import ReportFormat


def script(runner, targets=()):
    return deepswe_test_command(runner, targets).argv[2]


def test_python_puts_the_checkout_ahead_of_the_images_installed_package():
    # cattrs is installed editable from /app/src, so without this the container
    # imports /app/src/cattrs and every candidate patch is invisible.
    text = script("pytest")
    assert "PYTHONPATH=/tmp/work/src:/tmp/work" in text
    assert text.index("PYTHONPATH") < text.index("pytest")


def test_every_runner_works_inside_the_candidate_checkout():
    for runner in TEST_COMMANDS:
        assert "cd /tmp/work" in script(runner)


def test_node_runners_get_a_writable_node_modules_linking_each_package():
    # vite creates node_modules/.vite-temp; a single link to the read-only
    # /app/node_modules made that fail before any test ran.
    for runner in ("mocha", "jest", "vitest"):
        text = script(runner)
        assert "mkdir -p /tmp/work/node_modules" in text
        assert "ln -s /app/node_modules /tmp/work/node_modules" not in text


@pytest.mark.parametrize(
    "runner,expected,path",
    [
        ("go", ReportFormat.CTRF_JSON, "/tmp/ctrf.json"),
        ("pytest", ReportFormat.JUNIT_XML, "/tmp/report.xml"),
        ("mocha", ReportFormat.JUNIT_XML, "/tmp/report.xml"),
        ("jest", ReportFormat.CTRF_JSON, "ctrf/ctrf-report.json"),
        ("vitest", ReportFormat.JUNIT_XML, "/tmp/report.xml"),
        ("cargo-nextest", ReportFormat.JUNIT_XML, "/tmp/nextest-store/default/junit.xml"),
    ],
)
def test_reports_are_declared_where_each_runner_writes_them(runner, expected, path):
    report = deepswe_test_command(runner).report
    assert (report.format, report.path) == (expected, path)


@pytest.mark.parametrize(
    "runner,codes",
    [
        ("go", (1,)),
        ("pytest", (1,)),
        ("jest", (1,)),
        ("vitest", (1,)),
        # nextest: 100 means tests failed; 101, a failed build, is undeclared.
        ("cargo-nextest", (100,)),
    ],
)
def test_failure_exit_codes_are_what_each_runner_uses_for_failed_tests(runner, codes):
    assert deepswe_test_command(runner).failure_exit_codes == codes


def test_mocha_exits_with_its_failure_count():
    # Three failing tests exit 3; declaring only 1 made such a baseline a
    # harness error. 125 and above also mean signals, so they stay undeclared.
    codes = deepswe_test_command("mocha").failure_exit_codes
    assert 3 in codes and 124 in codes and 125 not in codes


def test_go_result_is_go_tests_exit_status_not_the_reporters():
    # go-ctrf-json-reporter exits 1 whenever a test failed, after writing the
    # full report. Acting on that exit would turn every real regression into a
    # harness error; a missing report is caught by the runner instead.
    text = script("go")
    assert "rc=$?" in text and text.endswith("exit $rc")
    assert "||" not in text


def test_jest_cannot_read_a_stale_report_left_in_the_checkout():
    assert "rm -rf /tmp/work/ctrf" in script("jest")


def test_targets_are_arguments_not_text_spliced_into_the_script():
    command = deepswe_test_command("pytest", ("tests/test_any.py", "-k", "not slow"))
    assert command.argv[3] == "deepswe-tests"
    assert command.argv[4:] == ("tests/test_any.py", "-k", "not slow")
    assert "tests/test_any.py" not in command.argv[2]


def test_an_unknown_runner_is_refused():
    with pytest.raises(ValueError, match="no verified DeepSWE test command"):
        deepswe_test_command("bun")


def package(tmp_path, test_script=None, **dependencies):
    manifest = {"devDependencies": dependencies}
    if test_script is not None:
        manifest["scripts"] = {"test": test_script}
    (tmp_path / "package.json").write_text(json.dumps(manifest), encoding="utf-8")
    return tmp_path


@pytest.mark.parametrize(
    "test_script,dependencies,expected",
    [
        # The real scripts of the tasks checked against their images.
        ("npm run check && jest", {"jest": "^29", "ts-jest": "^29"}, "jest"),
        ("pnpm lint && vitest run --coverage", {"vitest": "^4"}, "vitest"),
        ("mocha tests/*_tests.js tests/**/*_tests.js", {"mocha": "^10"}, "mocha"),
        # No script naming a runner: the one runner installed decides.
        ("node scripts/test.js", {"vitest": "^4"}, "vitest"),
        # ts-jest alone is not jest in the script.
        ("ts-jest-runner", {"jest": "^29"}, "jest"),
    ],
)
def test_node_runner_is_the_one_the_repository_declares(
    tmp_path, test_script, dependencies, expected
):
    checkout = package(tmp_path, test_script, **dependencies)
    assert deepswe_test_runner("typescript", checkout) == expected


def test_an_ambiguous_node_repository_is_refused_not_guessed(tmp_path):
    checkout = package(tmp_path, "node scripts/test.js", jest="^29", mocha="^10")
    with pytest.raises(ValueError, match="cannot tell which test runner"):
        deepswe_test_runner("javascript", checkout)


def test_go_python_and_rust_do_not_read_the_checkout(tmp_path):
    assert deepswe_test_runner("go", tmp_path) == "go"
    assert deepswe_test_runner("python", tmp_path) == "pytest"
    assert deepswe_test_runner("rust", tmp_path) == "cargo-nextest"
