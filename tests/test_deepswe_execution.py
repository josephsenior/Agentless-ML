"""The candidate checkout, not the image's own copy, must be the code under test."""

import json
import os
import shutil
import subprocess
import sys
from xml.etree import ElementTree

import pytest

from pathlib import Path

from agentless_ml.adapters.benchmarks.deepswe_execution import (
    TEST_COMMANDS,
    _KOOTA_MERGE,
    _PACKAGE_MERGE,
    _NODE_PACKAGE_MERGE,
    deepswe_test_command,
    deepswe_test_plan,
    deepswe_test_runner,
    deepswe_test_targets,
    load_test_overrides,
)

OVERRIDES = Path(__file__).resolve().parents[1] / "experiments" / "deepswe" / "test_overrides.json"
from agentless_ml.validation import ReportFormat, parse_report
from agentless_ml.validation import DockerTestRunner
from agentless_ml.workspace import LocalGitWorkspaceProvider


def script(runner, targets=()):
    return deepswe_test_command(runner, targets).argv[2]


def test_python_puts_the_checkout_ahead_of_the_images_installed_package():
    # cattrs is installed editable from /app/src, so without this the container
    # imports /app/src/cattrs and every candidate patch is invisible.
    text = script("pytest")
    assert "PYTHONPATH=/tmp/work/src:/tmp/work" in text
    assert text.index("PYTHONPATH") < text.index("pytest")

    stestr = script("stestr")
    assert "export PYTHONPATH=/tmp/work/src:/tmp/work" in stestr
    assert "stestr run --subunit" in stestr
    assert "subunit2junitxml" in stestr


def test_kea_preserves_the_public_babel_test_environment():
    text = script("kea-jest")
    assert text.startswith("export NODE_ENV=test BABEL_ENV=test;")
    assert text.index("BABEL_ENV=test") < text.index("/app/node_modules/.bin/jest")
    assert "testPathIgnorePatterns" not in text
    assert deepswe_test_command("kea-jest", ("test/jest/actions.js",)).argv[-1] == "test/jest/actions.js"


def test_langchain_uses_the_public_core_package_and_candidate_imports(tmp_path):
    override = load_test_overrides(OVERRIDES)["langchain-request-coalescing"]
    plan = deepswe_test_plan("python", tmp_path, override)
    assert plan.runner == "langchain-core-pytest" and plan.targets == ()
    text = plan.command().argv[2]
    assert "cd /tmp/work/libs/core" in text
    assert "PYTHONPATH=/tmp/work/libs/core:/tmp/work/libs/standard-tests" in text
    assert "is_relative_to(root)" in text
    assert text.index("refusing non-candidate import") < text.index("python -m pytest")
    assert "unset LANGCHAIN_TRACING_V2 LANGCHAIN_API_KEY LANGSMITH_API_KEY" in text
    assert "PYTEST_XDIST_AUTO_NUM_WORKERS=2" in text
    assert "-n auto --disable-socket --allow-unix-socket" in text
    assert "--junitxml=/tmp/report.xml tests/unit_tests/" in text
    assert "--only-core" not in text and "--only-extended" not in text
    with pytest.raises(ValueError, match="does not support narrowed targets"):
        deepswe_test_command("langchain-core-pytest", ("test_subset.py",))


def test_sql_formatter_generates_its_candidate_grammar_before_jest():
    text = script("sql-formatter-jest")
    assert "set -e; cd /tmp/work" in text
    generation = "node_modules/.bin/nearleyc src/parser/grammar.ne -o src/parser/grammar.ts"
    assert generation in text
    assert text.index("rm -rf /tmp/work/ctrf") < text.index(generation)
    assert text.index(generation) < text.index("/app/node_modules/.bin/jest")
    assert "cp /app/src" not in text
    assert "diagnostics=false" not in text
    assert deepswe_test_command("sql-formatter-jest").report == TEST_COMMANDS["jest"].report


def test_mnamer_restores_only_missing_generated_metadata():
    text = script("mnamer-pytest")
    assert "if [ ! -f mnamer/__version__.py ]; then" in text
    assert "cp /app/mnamer/__version__.py mnamer/__version__.py; fi" in text
    assert "PYTHONPATH=/tmp/work/src:/tmp/work" in text
    assert text.index("cp /app/mnamer/__version__.py") < text.index("python -m pytest")
    assert "SETUPTOOLS_SCM_PRETEND_VERSION" not in text
    assert deepswe_test_command("mnamer-pytest").report == TEST_COMMANDS["pytest"].report


def test_vitest_monorepo_builds_and_runs_candidate_packages():
    text = script("vitest-monorepo")
    assert "cp -a /app/node_modules node_modules" in text
    assert "/app/packages/*/node_modules /app/test/*/node_modules" in text
    assert 'readlink -f node_modules/vitest' in text
    assert '= "/tmp/work/packages/vitest"' in text
    assert text.index("pnpm run build") < text.index("cd test/core")
    assert "node /tmp/work/packages/vitest/vitest.mjs run --project threads" in text
    assert "/app/node_modules/.bin/vitest run" not in text
    assert deepswe_test_command("vitest-monorepo", ("test/basic.test.ts",)).argv[-1] == "test/basic.test.ts"


def test_one_unimportable_test_module_does_not_empty_a_python_inventory():
    # cattrs: six modules import packages the image lacks; without this flag
    # pytest stops before running any of the suite.
    assert "--continue-on-collection-errors" in script("pytest")


def test_every_runner_works_inside_the_candidate_checkout():
    for runner in TEST_COMMANDS:
        assert "cd /tmp/work" in script(runner)


def test_node_runners_get_a_writable_node_modules_linking_each_package():
    # vite creates node_modules/.vite-temp; a single link to the read-only
    # /app/node_modules made that fail before any test ran.
    for runner in ("mocha", "mocha-json", "jest", "vitest", "vitest-writable"):
        text = script(runner)
        assert "mkdir -p /tmp/work/node_modules" in text
        assert "ln -s /app/node_modules /tmp/work/node_modules" not in text


def test_koota_runner_copies_relative_workspace_links_into_the_candidate():
    text = script("koota-vitest")
    assert "cp -a /app/node_modules node_modules" in text
    assert "cp -a /app/packages/react/node_modules packages/react/node_modules" in text
    assert 'readlink -f packages/react/node_modules/@koota/core' in text
    assert '= "/tmp/work/packages/core"' in text
    assert "cd packages/core" in text and "cd packages/react" in text
    assert "--environment=jsdom" in text


def test_koota_reports_keep_same_named_tests_separate(tmp_path):
    for package in ("core", "react"):
        (tmp_path / f"{package}.xml").write_text(
            '<testsuite><testcase classname="suite" name="same" /></testsuite>',
            encoding="utf-8",
        )
    merged = tmp_path / "merged.xml"
    subprocess.run(
        [sys.executable, "-c", _KOOTA_MERGE, str(merged),
         str(tmp_path / "core.xml"), str(tmp_path / "react.xml")],
        check=True,
    )
    names = [case.get("classname") for case in ElementTree.parse(merged).iter("testcase")]
    assert names == ["core/suite", "react/suite"]


def test_koota_runner_refuses_a_selector_it_cannot_apply_to_both_packages():
    with pytest.raises(ValueError, match="does not support narrowed targets"):
        deepswe_test_command("koota-vitest", ("tests/entity.test.ts",))


@pytest.mark.parametrize(
    "runner,expected,path",
    [
        ("go", ReportFormat.CTRF_JSON, "/tmp/ctrf.json"),
        ("pytest", ReportFormat.JUNIT_XML, "/tmp/report.xml"),
        ("stestr", ReportFormat.JUNIT_XML, "/tmp/report.xml"),
        ("mocha", ReportFormat.JUNIT_XML, "/tmp/report.xml"),
        ("mocha-json", ReportFormat.MOCHA_JSON, "/tmp/mocha-report.json"),
        ("jest", ReportFormat.CTRF_JSON, "ctrf/ctrf-report.json"),
        ("vitest", ReportFormat.JUNIT_XML, "/tmp/report.xml"),
        ("vitest-writable", ReportFormat.JUNIT_XML, "/tmp/report.xml"),
        ("koota-vitest", ReportFormat.JUNIT_XML, "/tmp/report.xml"),
        ("cargo-nextest", ReportFormat.JUNIT_XML, "/tmp/nextest-store/default/junit.xml"),
        ("pest-cargo-nextest", ReportFormat.JUNIT_XML, "/tmp/nextest-store/default/junit.xml"),
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
        ("koota-vitest", (1,)),
        # nextest: 100 means tests failed; 101, a failed build, is undeclared.
        ("cargo-nextest", (100,)),
        ("pest-cargo-nextest", (100,)),
    ],
)
def test_failure_exit_codes_are_what_each_runner_uses_for_failed_tests(runner, codes):
    assert deepswe_test_command(runner).failure_exit_codes == codes


def test_mocha_exits_with_its_failure_count():
    # Three failing tests exit 3; declaring only 1 made such a baseline a
    # harness error. 125 and above also mean signals, so they stay undeclared.
    codes = deepswe_test_command("mocha").failure_exit_codes
    assert 3 in codes and 124 in codes and 125 not in codes


def test_pest_bootstrap_builds_candidate_before_the_unchanged_test_schedule(tmp_path):
    override = load_test_overrides(OVERRIDES)["pest-character-class-coalescing"]
    plan = deepswe_test_plan("rust", tmp_path, override)
    assert plan.runner == "pest-cargo-nextest"
    assert plan.targets == ()
    text = plan.command().argv[2]
    assert "cd /tmp/work && " in text
    assert "mkdir -p /tmp/target && ln -s /tmp/target target || exit 125" in text
    bootstrap = "cargo build --package pest_bootstrap || exit 125"
    assert text.index(bootstrap) < text.index("cargo nextest run")
    assert text.count("CARGO_HOME=/tmp/cargo-home") == 2
    assert text.count("CARGO_TARGET_DIR=/tmp/target") == 2
    assert text.count("CARGO_NET_OFFLINE=true") == 2
    assert text.endswith('cargo nextest run --config-file /tmp/nextest.toml --no-fail-fast "$@"')


def test_go_result_is_go_tests_exit_status_not_the_converter():
    # The converter's exit only signals whether it produced a valid report;
    # go test's own exit status remains the public-test result.
    text = script("go")
    assert "rc=$?" in text and text.endswith("exit $rc")
    assert "|| exit 125" in text


def test_go_build_events_do_not_become_test_cases():
    text = script("go")
    assert text.index("grep '\"Action\":\"build-output\"'") < text.index("go run")
    assert '\"Action\":\"build-' in text
    assert 'event.Test == ""' in text  # Package/build outcomes are not individual tests.
    assert "build-output" in text  # Retain compiler diagnostics for failed builds.


def test_go_report_conversion_streams_only_terminal_test_events():
    text = script("go")
    assert "json.NewDecoder" in text
    assert 'case "pass":' in text and 'status = "passed"' in text
    assert 'case "fail":' in text and 'status = "failed"' in text
    assert 'case "skip":' in text and 'status = "skipped"' in text
    assert "go-ctrf-json-reporter" not in text


@pytest.mark.skipif(shutil.which("go") is None, reason="Go toolchain is not installed")
def test_go_stream_converter_compiles_and_preserves_test_outcomes(tmp_path):
    source = Path(__file__).resolve().parents[1] / (
        "src/agentless_ml/adapters/benchmarks/go_json_to_ctrf.go"
    )
    events = tmp_path / "events.jsonl"
    report = tmp_path / "report.json"
    events.write_text(
        '\n'.join((
            '{"Action":"run","Package":"example/pkg","Test":"TestPass"}',
            '{"Action":"output","Package":"example/pkg","Test":"TestPass","Output":"verbose log"}',
            '{"Action":"pass","Package":"example/pkg","Test":"TestPass"}',
            '{"Action":"skip","Package":"example/pkg","Test":"TestSkip"}',
            '{"Action":"fail","Package":"example/pkg","Test":"TestFail"}',
            '{"Action":"fail","Package":"example/build","Output":"compile error"}',
        )) + '\n',
        encoding="utf-8",
    )
    subprocess.run(
        ["go", "run", str(source), str(events), str(report)],
        check=True,
        timeout=60,
    )

    cases = parse_report(report.read_bytes(), ReportFormat.CTRF_JSON)
    assert [(case.test_id, case.status.value) for case in cases] == [
        ("example/pkg::TestPass", "passed"),
        ("example/pkg::TestSkip", "skipped"),
        ("example/pkg::TestFail", "failed"),
    ]


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


def test_koota_workspace_runner_requires_both_declared_package_scripts(tmp_path):
    checkout = package(tmp_path, "pnpm -F core test run && pnpm -F react test run")
    core = checkout / "packages/core"
    react = checkout / "packages/react"
    core.mkdir(parents=True)
    react.mkdir(parents=True)
    (core / "package.json").write_text('{"scripts":{"test":"vitest"}}', encoding="utf-8")
    (react / "package.json").write_text(
        '{"scripts":{"test":"vitest --environment=jsdom"}}', encoding="utf-8"
    )
    assert deepswe_test_runner("typescript", checkout) == "koota-vitest"
    (react / "package.json").write_text('{"scripts":{"test":"jest"}}', encoding="utf-8")
    with pytest.raises(ValueError, match="cannot tell which test runner"):
        deepswe_test_runner("typescript", checkout)


def test_go_python_and_rust_do_not_read_the_checkout(tmp_path):
    assert deepswe_test_runner("go", tmp_path) == "go"
    assert deepswe_test_runner("python", tmp_path) == "pytest"
    assert deepswe_test_runner("rust", tmp_path) == "cargo-nextest"


@pytest.mark.parametrize(
    "script,expected",
    [
        # testem's real script.
        ("mocha tests/*_tests.js tests/**/*_tests.js", ("tests/*_tests.js", "tests/**/*_tests.js")),
        # Reporter and watch flags would replace the report this command reads.
        ("mocha -R spec --reporter-option foo=1 --watch test/", ("test/",)),
        ("mocha --reporter=dot --timeout 5000 test/", ("--timeout", "5000", "test/")),
        # The runner is found after other steps and behind a path.
        ("npm run lint && ./node_modules/.bin/_mocha test/unit", ("test/unit",)),
    ],
)
def test_mocha_targets_are_what_the_test_script_passes_it(tmp_path, script, expected):
    checkout = package(tmp_path, script, mocha="^10")
    assert deepswe_test_targets("mocha", checkout) == expected


def test_other_runners_use_their_own_discovery_and_go_every_package(tmp_path):
    assert deepswe_test_targets("go", tmp_path) == ("./...",)
    for runner in ("pytest", "jest", "vitest", "cargo-nextest"):
        assert deepswe_test_targets(runner, tmp_path) == ()


def test_a_mocha_repository_whose_script_never_calls_mocha_is_refused(tmp_path):
    with pytest.raises(ValueError, match="no mocha invocation"):
        deepswe_test_targets("mocha", package(tmp_path, "node run-tests.js", mocha="^10"))


def test_an_override_appends_arguments_and_keeps_its_reason(tmp_path):
    checkout = package(tmp_path, "npm run check && jest", jest="^29")
    override = {"arguments": ["--testPathIgnorePatterns=rollup.test"], "reason": "needs a build"}
    plan = deepswe_test_plan("typescript", checkout, override)
    assert (plan.runner, plan.targets) == ("jest", ("--testPathIgnorePatterns=rollup.test",))
    assert plan.override_reason == "needs a build"
    assert plan.command().argv[4:] == ("--testPathIgnorePatterns=rollup.test",)


def test_an_override_can_replace_the_derived_targets(tmp_path):
    plan = deepswe_test_plan("go", tmp_path, {"targets": ["."], "reason": "root package only"})
    assert plan.targets == (".",)


def test_the_checked_in_overrides_are_well_formed_and_explained():
    overrides = load_test_overrides(OVERRIDES)
    assert set(overrides) == {
        "langchain-request-coalescing",
        "pwntools-tube-multiplexing",
        "optique-conditional-option-dependencies",
        "valibot-recursive-schema-composition",
        "arktype-json-schema-refs-dependencies",
        "clack-async-autocomplete-options",
        "pest-character-class-coalescing",
        "awilix-async-container-initialization",
        "bandit-structured-nosec-directives",
        "csstree-shorthand-expansion-compression",
        "fastapi-implicit-head-options",
        "prometheus-transactional-reload-status",
        "prometheus-typed-label-sorting",
        "returns-validated-error-accumulation",
        "true-myth-iterable-collection-combinators",
        "claude-code-by-agents-recursive-delegation",
        "quill-shared-toolbar-focus",
        "cliffy-config-file-parsing",
        "ink-grid-box-layout",
        "kysely-window-grouping-helpers",
        "yjs-map-conflict-detection",
        "kea-atomic-signal-selectors",
        "sql-formatter-bigquery-pipe-formatting",
        "mnamer-daemon-watch-lifecycle",
        "vitest-duration-sharding",
    }
    assert all(len(entry["reason"]) > 40 for entry in overrides.values())


def test_prometheus_overrides_name_their_intended_packages():
    overrides = load_test_overrides(OVERRIDES)
    assert overrides["prometheus-transactional-reload-status"]["runner"] == "go-module"
    assert overrides["prometheus-transactional-reload-status"]["tmpfs_mb"] == 8192
    assert overrides["prometheus-transactional-reload-status"]["targets"] == [
        "./cmd/prometheus",
    ]
    assert overrides["prometheus-typed-label-sorting"]["targets"] == ["./promql/..."]


def test_runner_override_changes_the_command_without_changing_targets(tmp_path):
    override = {"runner": "go-module", "targets": ["./cmd/prometheus"], "reason": "image mode"}
    plan = deepswe_test_plan("go", tmp_path, override)
    assert (plan.runner, plan.targets) == ("go-module", ("./cmd/prometheus",))
    assert "GOWORK=off" in plan.command().argv[2]


def test_reviewed_runner_override_works_without_a_root_node_manifest(tmp_path):
    # Cliffy has deno.json instead of package.json; automatic Node discovery
    # must not run before its explicit, reviewed override.
    plan = deepswe_test_plan("typescript", tmp_path, {"runner": "deno", "reason": "Deno project"})
    assert plan.runner == "deno"
    assert plan.command().report.path == "/tmp/report.xml"


def test_nested_package_reports_keep_same_named_tests_separate(tmp_path):
    report = '<testsuites><testsuite><testcase classname="suite" name="same" /></testsuite></testsuites>'
    arguments = []
    for package in ("backend", "frontend"):
        path = tmp_path / f"{package}.xml"
        path.write_text(report, encoding="utf-8")
        arguments.extend((package, str(path)))
    merged = tmp_path / "merged.xml"
    subprocess.run([sys.executable, "-c", _PACKAGE_MERGE, str(merged), *arguments], check=True)
    names = [case.get("classname") for case in ElementTree.parse(merged).iter("testcase")]
    assert names == ["backend/suite", "frontend/suite"]


def test_package_merge_keeps_root_cases_and_nested_suites_exactly_once(tmp_path):
    report = tmp_path / "node.xml"
    report.write_text(
        '<testsuites><testcase name="visible" />'
        '<testcase name="failure"><failure message="intentional" /></testcase>'
        '<testsuite name="outer"><testsuite name="inner">'
        '<testcase classname="suite" name="nested"><skipped /></testcase>'
        '</testsuite></testsuite></testsuites>', encoding="utf-8",
    )
    merged = tmp_path / "merged.xml"
    subprocess.run(
        [sys.executable, "-c", _PACKAGE_MERGE, str(merged), "node", str(report)],
        check=True,
    )
    cases = list(ElementTree.parse(merged).iter("testcase"))
    assert len(cases) == 3
    assert [case.get("name") for case in cases] == ["visible", "failure", "nested"]
    outcomes = parse_report(merged.read_bytes(), ReportFormat.JUNIT_XML)
    assert [case.status.value for case in outcomes] == ["passed", "failed", "skipped"]


def test_node_merge_keeps_file_and_nested_suite_context_in_test_ids(tmp_path):
    report = tmp_path / "node.xml"
    report.write_text(
        '<testsuites><testcase name="root" file="/tmp/work/src/a.test.ts">'
        '<failure /></testcase><testsuite name="first">'
        '<testcase classname="test" name="same" file="/tmp/work/src/a.test.ts" />'
        '</testsuite><testsuite name="second">'
        '<testcase classname="test" name="same" file="/tmp/work/src/a.test.ts" />'
        '<testcase classname="test" name="same" file="/tmp/work/src/b.test.ts" />'
        '</testsuite></testsuites>', encoding="utf-8",
    )
    merged = tmp_path / "merged.xml"
    subprocess.run(
        [sys.executable, "-c", _NODE_PACKAGE_MERGE, str(merged), "pkg", str(report)],
        check=True,
    )
    cases = parse_report(merged.read_bytes(), ReportFormat.JUNIT_XML)
    assert len(cases) == 4
    assert cases[0].status.value == "failed"
    assert {case.test_id for case in cases[1:]} == {
        "pkg/src/a.test.ts/first::same", "pkg/src/a.test.ts/second::same",
        "pkg/src/b.test.ts/second::same",
    }


@pytest.mark.parametrize("runner", (
    "agentrooms-vitest", "quill-vitest", "clack-vitest", "valibot-vitest", "optique-node",
))
def test_nested_suites_refuse_unsupported_target_filtering(runner):
    with pytest.raises(ValueError, match="does not support narrowed targets"):
        deepswe_test_command(runner, ("some-test.ts",))


def test_arktype_alias_keeps_public_mocha_arguments_and_candidate_links(tmp_path):
    override = load_test_overrides(OVERRIDES)["arktype-json-schema-refs-dependencies"]
    plan = deepswe_test_plan("typescript", tmp_path, override)
    assert plan.targets == ("--exclude", "ark/attest/**/*.test.*", "--skipTypes")
    command = plan.command()
    text = command.argv[2]
    assert "cp -a /app/node_modules node_modules" in text
    assert "/app/ark/*/node_modules" in text
    assert 'package=${entry#/app/}' in text
    assert "node node_modules/mocha/bin/mocha.js" in text
    assert "--reporter-option output=/tmp/mocha-report.json" in text
    assert command.report.format == ReportFormat.MOCHA_JSON
    assert command.argv[-3:] == plan.targets


def test_clack_builds_before_both_public_package_suites(tmp_path):
    override = load_test_overrides(OVERRIDES)["clack-async-autocomplete-options"]
    plan = deepswe_test_plan("typescript", tmp_path, override)
    assert plan.targets == ()
    text = plan.command().argv[2]
    assert "cp -a /app/packages/core/node_modules packages/core/node_modules" in text
    assert "cp -a /app/packages/prompts/node_modules packages/prompts/node_modules" in text
    assert text.index("pnpm run build || exit 125") < text.index("cd packages/core && npm exec")
    assert "cd packages/prompts && npm exec --offline -- vitest run" in text
    assert "core /tmp/core.xml prompts /tmp/prompts.xml" in text


def test_valibot_keeps_all_three_suites_and_public_typechecks(tmp_path):
    override = load_test_overrides(OVERRIDES)["valibot-recursive-schema-composition"]
    plan = deepswe_test_plan("typescript", tmp_path, override)
    assert plan.targets == ()
    text = plan.command().argv[2]
    assert text.index("cd library && npm run build") < text.index("vitest run")
    assert "cd library && npm exec --offline -- vitest run --typecheck" in text
    assert "cd packages/to-json-schema && npm exec --offline -- vitest run --typecheck" in text
    assert "cd codemod/zod-to-valibot && npm exec --offline -- vitest run" in text
    assert "cp -a /app/codemod/zod-to-valibot/node_modules codemod/zod-to-valibot/node_modules" in text
    assert "to-json-schema /tmp/to-json-schema.xml zod-to-valibot /tmp/zod-to-valibot.xml" in text


def test_optique_uses_its_public_node_alternative_with_all_nine_packages(tmp_path):
    override = load_test_overrides(OVERRIDES)["optique-conditional-option-dependencies"]
    plan = deepswe_test_plan("typescript", tmp_path, override)
    assert plan.runner == "optique-node" and plan.targets == ()
    text = plan.command().argv[2]
    assert "pnpm -r --filter './packages/*' run build || exit 125" in text
    assert text.index("run build") < text.index("--experimental-transform-types --test")
    assert text.count("--test-reporter=junit") == 9
    for package in ("core", "config", "git", "logtape", "man", "run", "temporal", "valibot", "zod"):
        assert f"cd packages/{package} && node" in text
        assert f"{package} /tmp/{package}.xml" in text
    assert "--test-reporter-destination=/tmp/man.xml 'src/**/*.test.ts'" in text
    assert plan.command().report.format == ReportFormat.JUNIT_XML


@pytest.mark.skipif(
    not os.environ.get("AGENTLESS_DELEGATED_TASK_REPOSITORIES"),
    reason="opt-in pinned delegated-runner candidate isolation checks",
)
@pytest.mark.parametrize(
    "task_id,base_commit,image_id,source_path,probe_path,probe",
    [
        (
            "arktype-json-schema-refs-dependencies",
            "04355e8b26d1ad5264ef62314a2bc46c4de58ed8",
            "sha256:e0b0410d828b816474cfb89a448c448f15cf7d617c3fbddfacd45a1c1b232ef9",
            "ark/util/index.ts",
            "ark/type/__tests__/agentless-candidate-probe.test.ts",
            "import assert from 'node:assert/strict';\n"
            "import { agentlessCandidateSourceProbe } from '@ark/util';\n"
            "it('agentless candidate source visible', () => "
            "assert.equal(agentlessCandidateSourceProbe, true));\n"
            "it('agentless candidate failure detected', () => { "
            "assert.equal(agentlessCandidateSourceProbe, true); "
            "throw Error('intentional candidate failure'); });\n",
        ),
        (
            "clack-async-autocomplete-options",
            "8a96e2dcd7f821d1250b58cf71c327679f94de25",
            "sha256:32a72ef7d4a9d3ae8937aef9c42e18166284c817c8edf137d66772e4f34abf74",
            "packages/core/src/index.ts",
            "packages/prompts/test/agentless-candidate-probe.test.ts",
            "import { it, expect } from 'vitest';\n"
            "import { agentlessCandidateSourceProbe } from '@clack/core';\n"
            "it('agentless candidate source visible', () => "
            "expect(agentlessCandidateSourceProbe).toBe(true));\n"
            "it('agentless candidate failure detected', () => { "
            "expect(agentlessCandidateSourceProbe).toBe(true); "
            "throw Error('intentional candidate failure'); });\n",
        ),
        (
            "optique-conditional-option-dependencies",
            "14bbe4efc7ded67932771b9ca18d9d637bb4cf27",
            "sha256:081a0ad371727807a1a3ba2613345b4876fd0e148bbf78cd70f013918be28084",
            "packages/core/src/index.ts",
            "packages/run/src/agentless-candidate-probe.test.ts",
            "import { it } from 'node:test';\n"
            "import assert from 'node:assert/strict';\n"
            "import { agentlessCandidateSourceProbe } from '@optique/core';\n"
            "it('agentless candidate source visible', () => "
            "assert.equal(agentlessCandidateSourceProbe, true));\n"
            "it('agentless candidate failure detected', () => { "
            "assert.equal(agentlessCandidateSourceProbe, true); "
            "throw Error('intentional candidate failure'); });\n",
        ),
        (
            "valibot-recursive-schema-composition",
            "50016c77c808f9ca80391cf1abc96cc5416cf57d",
            "sha256:a52ea332702ee2470bf584a9d07be8064466c110f16230242ba6863b62c7154d",
            "library/src/index.ts",
            "packages/to-json-schema/src/agentless-candidate-probe.test.ts",
            "import { it, expect } from 'vitest';\n"
            "import { agentlessCandidateSourceProbe } from 'valibot';\n"
            "it('agentless candidate source visible', () => "
            "expect(agentlessCandidateSourceProbe).toBe(true));\n"
            "it('agentless candidate failure detected', () => { "
            "expect(agentlessCandidateSourceProbe).toBe(true); "
            "throw Error('intentional candidate failure'); });\n",
        ),
    ],
)
def test_delegated_runner_detects_candidate_workspace_source(
    tmp_path, task_id, base_commit, image_id, source_path, probe_path, probe
):
    repositories = Path(os.environ["AGENTLESS_DELEGATED_TASK_REPOSITORIES"])
    provider = LocalGitWorkspaceProvider(
        repositories / task_id, base_commit, tmp_path / "workspaces"
    )
    artifacts = Path(os.environ.get(
        "AGENTLESS_DELEGATED_TASK_ARTIFACTS", str(tmp_path / "logs")
    )) / task_id
    runner = DockerTestRunner(
        image_id, artifacts, memory_mb=8192, cpus=2, tmpfs_mb=4096,
        pids_limit=2048, run_as_image_user=True,
    )
    override = load_test_overrides(OVERRIDES)[task_id]
    with provider.create() as workspace:
        source = workspace.path / source_path
        source.write_text(
            source.read_text(encoding="utf-8")
            + "\nexport const agentlessCandidateSourceProbe = true;\n",
            encoding="utf-8",
        )
        probe_file = workspace.path / probe_path
        probe_file.parent.mkdir(parents=True, exist_ok=True)
        probe_file.write_text(probe, encoding="utf-8")
        plan = deepswe_test_plan("typescript", workspace.path, override)
        execution = runner.run(workspace.path, plan.command(timeout_seconds=600))
    cases = execution.result.test_cases
    assert execution.result.status.value == "fail", execution.message
    visible = [case for case in cases if "agentless candidate source visible" in case.test_id]
    failed = [case for case in cases if "agentless candidate failure detected" in case.test_id]
    assert len(visible) == 1 and visible[0].status.value == "passed"
    assert len(failed) == 1 and failed[0].status.value == "failed"


@pytest.mark.parametrize(
    "entry,message",
    [
        ({"arguments": ["-x"]}, "needs a reason"),
        ({"reason": "why", "arguments": ["-x"], "image": "other"}, "unknown keys"),
        ({"reason": "why"}, "changes nothing"),
        ({"reason": "why", "arguments": "-x"}, "list of strings"),
        ({"reason": "why", "runner": []}, "unknown runner"),
        ({"reason": "why", "tmpfs_mb": 0}, "positive integer"),
        ({"reason": "why", "tmpfs_mb": "8192"}, "positive integer"),
    ],
)
def test_malformed_overrides_are_refused(tmp_path, entry, message):
    path = tmp_path / "overrides.json"
    path.write_text(json.dumps({"task": entry}), encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        load_test_overrides(path)


def test_go_workspace_targets_every_module(tmp_path):
    # arcane: go.work ties three modules together and the root is not a module,
    # so ./... matched nothing and go test exited before running a test.
    (tmp_path / "go.work").write_text(
        "go 1.26.0\n\n// the backend\nuse (\n\t./backend\n\t./cli\n\t./types\n)\nuse ./tools\n",
        encoding="utf-8",
    )
    assert deepswe_test_targets("go", tmp_path) == (
        "./backend/...", "./cli/...", "./types/...", "./tools/...",
    )


def test_go_command_leaves_module_mode_to_go():
    # Forcing -mod=mod is refused in workspace mode.
    assert "-mod=" not in script("go")


def test_go_command_clears_image_goflags_only_for_workspaces():
    # Prometheus's image exports GOFLAGS=-mod=mod; go.work cannot use it.
    text = script("go")
    assert "if [ -f go.work ]; then export GOFLAGS=; fi" in text
    assert text.index("export GOFLAGS=") < text.index("go test -json")


def test_go_module_command_uses_the_images_offline_module_setup():
    text = script("go-module")
    assert "export GOWORK=off" in text
    assert "cp -a /opt/gocache/. /tmp/go-build/" in text
    assert "export GOFLAGS=" not in text
    assert deepswe_test_command("go-module").report == deepswe_test_command("go").report
