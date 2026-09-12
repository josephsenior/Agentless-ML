"""Fixed recorded localization, repair, validation and selection across languages."""

from __future__ import annotations

import hashlib
import json
import math
import time
import uuid
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from agentless_ml.adapters.languages import get_language_adapter
from agentless_ml.localization import (
    construct_selected_context,
    extract_code_blocks,
    parse_file_locations,
    parse_locations_for_files,
    render_file_localization_prompt,
    render_symbol_localization_prompt,
)
from agentless_ml.localization.context import render_project_tree
from agentless_ml.localization.edit import (
    parse_edit_locations,
    render_edit_localization_prompt,
)
from agentless_ml.repair import (
    EditApplicationError,
    EditParseError,
    apply_search_replace_edits,
    build_patch_candidate,
    build_repair_prompt,
    build_unified_diff,
    parse_search_replace_edits,
    select_candidate,
)
from agentless_ml.schemas import (
    FinalPrediction,
    PatchCandidate,
    RunRecord,
    TaskSpec,
    ValidationKind,
    ValidationStatus,
)
from agentless_ml.validation import (
    DockerTestRunner,
    PublicTestCommand,
    RegressionTest,
    validate_candidate,
)
from agentless_ml.validation.regression import (
    parse_regression_exclusions,
    render_regression_selection_prompt,
)
from agentless_ml.validation.reproduction import (
    ReproductionSpec,
    parse_reproduction_source,
    render_reproduction_prompt,
    reproduction_file,
    select_reproduction_source,
)
from agentless_ml.workspace import LocalGitWorkspaceProvider


class WorkflowError(RuntimeError):
    """A recorded fixed trajectory cannot produce an auditable prediction."""


@dataclass(frozen=True, slots=True)
class RecordedEditSample:
    edit_localization: str
    repairs: tuple[str, ...]

    def __post_init__(self):
        if not self.edit_localization.strip():
            raise ValueError("edit localization response must not be empty")
        if not self.repairs or any(not response.strip() for response in self.repairs):
            raise ValueError("each edit sample needs nonempty repair responses")


@dataclass(frozen=True, slots=True)
class RecordedStageResponses:
    file_localization: str
    symbol_localization: str
    repairs: tuple[str, ...] = ()
    source: str = "recorded"
    edit_localization: str | None = None
    edit_samples: tuple[RecordedEditSample, ...] = ()
    regression_exclusions: str | None = None
    reproduction_test: str | None = None
    reproduction_samples: tuple[str, ...] = ()

    def __post_init__(self):
        if not self.file_localization.strip() or not self.symbol_localization.strip():
            raise ValueError("localization responses must not be empty")
        if self.reproduction_samples and self.reproduction_test is not None:
            raise ValueError("do not mix reproduction_samples with reproduction_test")
        if self.edit_samples and (self.repairs or self.edit_localization is not None):
            raise ValueError(
                "edit_samples cannot be mixed with legacy repair/edit fields"
            )
        if not self.edit_samples and (
            not self.repairs or any(not response.strip() for response in self.repairs)
        ):
            raise ValueError("at least one nonempty repair response is required")
        if not self.source.strip():
            raise ValueError("response source must not be empty")
        if self.edit_localization is not None and not self.edit_localization.strip():
            raise ValueError("edit localization response must not be empty")


@dataclass(frozen=True, slots=True)
class CandidateAttempt:
    candidate_id: str
    sample_index: int
    status: str
    message: str = ""
    candidate: PatchCandidate | None = None
    localization_rank: int = 0


@dataclass(frozen=True, slots=True)
class WorkflowResult:
    prediction: FinalPrediction
    run: RunRecord
    attempts: tuple[CandidateAttempt, ...]
    selected_files: tuple[str, ...]
    selection_reason: str
    artifact_directory: str


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _jsonable(child) for key, child in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(child) for child in value]
    return value


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(_jsonable(value), indent=2) + "\n", encoding="utf-8")


class FixedWorkflowController:
    """Execute one predetermined run from immutable recorded responses.

    The response bundle contains data only. The controller has no model client,
    retry branch, test-feedback loop, or hidden-verifier interface.
    """

    def __init__(
        self,
        *,
        task: TaskSpec,
        source_repository: Path,
        workspace_root: Path,
        artifact_root: Path,
        runner: DockerTestRunner,
        public_commands: tuple[PublicTestCommand, ...],
        implementation_revision: str,
        harness_revision: str,
        model_name: str,
        regression_tests: tuple[RegressionTest, ...] = (),
        reproduction_spec: ReproductionSpec | None = None,
    ):
        self.adapter = get_language_adapter(task.language)
        if not public_commands and not regression_tests and reproduction_spec is None:
            raise ValueError("public test schedule must not be empty")
        if len({test.test_id for test in regression_tests}) != len(regression_tests):
            raise ValueError("regression test IDs must be unique")
        if regression_tests and any(
            command.kind == ValidationKind.REGRESSION for command in public_commands
        ):
            raise ValueError(
                "use the regression inventory instead of mixing fixed regression commands"
            )
        if any(
            not value.strip()
            for value in (implementation_revision, harness_revision, model_name)
        ):
            raise ValueError(
                "implementation, harness, and model provenance are required"
            )
        if runner.image_reference != task.container_image:
            raise ValueError("runner image reference does not match the task")
        if task.container_digest and runner.image_id != task.container_digest:
            raise ValueError("resolved container image does not match the task digest")
        self.task = task
        self.provider = LocalGitWorkspaceProvider(
            source_repository, task.base_commit, workspace_root
        )
        self.artifact_root = Path(artifact_root).resolve()
        source = self.provider.source_repository
        workspace = self.provider.workspace_root
        if (
            self.artifact_root == source
            or self.artifact_root.is_relative_to(source)
            or source.is_relative_to(self.artifact_root)
            or self.artifact_root == workspace
            or self.artifact_root.is_relative_to(workspace)
            or workspace.is_relative_to(self.artifact_root)
        ):
            raise ValueError("source, workspace, and artifact roots must be separate")
        self.runner = runner
        self.public_commands = public_commands
        self.regression_tests = regression_tests
        self.reproduction_spec = reproduction_spec
        if reproduction_spec is not None and any(
            command.kind == ValidationKind.REPRODUCTION for command in public_commands
        ):
            raise ValueError("do not mix generated and fixed reproduction commands")
        self.implementation_revision = implementation_revision
        self.harness_revision = harness_revision
        self.model_name = model_name

    def _prepare_reproduction_samples(
        self, samples: tuple[str, ...], directory: Path
    ) -> str:
        spec = self.reproduction_spec
        prompt = render_reproduction_prompt(
            self.task.problem_statement, self.task.language, spec
        )
        (directory / "reproduction-generation.txt").write_text(prompt, encoding="utf-8")
        verified = {}
        attempts = []
        for index, response in enumerate(samples):
            sample_directory = directory / "reproduction-samples" / str(index)
            sample_directory.mkdir(parents=True)
            try:
                source = parse_reproduction_source(response, self.task.language)
            except ValueError as exc:
                attempts.append(
                    {
                        "sample_index": index,
                        "status": "parse_error",
                        "message": str(exc),
                    }
                )
                _write_json(directory / "reproduction-attempts.json", attempts)
                continue
            _write_json(
                sample_directory / "source.json",
                {
                    "source": source,
                    "source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
                    "spec": asdict(spec),
                },
            )
            with self.provider.create() as workspace:
                with reproduction_file(workspace.path, spec, source):
                    execution = self.runner.run(
                        workspace.path,
                        spec.command,
                        artifact_root=sample_directory / "reproduction-baseline",
                    )
                _write_json(
                    sample_directory / "baseline.json",
                    {
                        "result": asdict(execution.result),
                        "workspace": asdict(workspace.provenance),
                        "artifact_directory": execution.artifact_directory,
                    },
                )
            status = execution.result.status
            attempts.append({"sample_index": index, "status": status.value})
            _write_json(directory / "reproduction-attempts.json", attempts)
            if status == ValidationStatus.FAIL:
                verified[index] = source
            elif status != ValidationStatus.PASS:
                raise WorkflowError(
                    f"reproduction sample {index} has an infrastructure failure"
                )
        try:
            selected_index, votes = select_reproduction_source(verified)
        except ValueError as exc:
            raise WorkflowError(str(exc)) from exc
        source = verified[selected_index]
        _write_json(
            directory / "reproduction-selection.json",
            {
                "selected_sample_index": selected_index,
                "vote_count": votes,
                "eligible_sample_indices": list(verified),
                "voting_key": "exact-source-v1",
                "source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
            },
        )
        _write_json(
            directory / "reproduction-source.json",
            {
                "spec": asdict(spec),
                "source": source,
                "source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
            },
        )
        return source

    def run(self, responses: RecordedStageResponses) -> WorkflowResult:
        started_at = datetime.now(UTC)
        started = time.monotonic()
        run_id = "run-" + uuid.uuid4().hex
        directory = self.artifact_root / run_id
        directory.mkdir(parents=True)
        try:
            _write_json(directory / "responses.json", asdict(responses))
            if bool(self.regression_tests) != (
                responses.regression_exclusions is not None
            ):
                raise WorkflowError(
                    "regression inventory and recorded exclusions must be supplied together"
                )
            public_commands = self.public_commands
            reproduction = None
            if (self.reproduction_spec is not None) != (
                responses.reproduction_test is not None
                or bool(responses.reproduction_samples)
            ):
                raise WorkflowError(
                    "reproduction specification and recorded source must be supplied together"
                )
            if self.reproduction_spec is not None and responses.reproduction_samples:
                source = self._prepare_reproduction_samples(
                    responses.reproduction_samples, directory
                )
                reproduction = (self.reproduction_spec, source)
                public_commands += (self.reproduction_spec.command,)
            elif self.reproduction_spec is not None:
                spec = self.reproduction_spec
                prompt = render_reproduction_prompt(
                    self.task.problem_statement, self.task.language, spec
                )
                (directory / "reproduction-generation.txt").write_text(
                    prompt, encoding="utf-8"
                )
                try:
                    source = parse_reproduction_source(
                        responses.reproduction_test, self.task.language
                    )
                    _write_json(
                        directory / "reproduction-source.json",
                        {
                            "spec": asdict(spec),
                            "source": source,
                            "source_sha256": hashlib.sha256(
                                source.encode("utf-8")
                            ).hexdigest(),
                        },
                    )
                    with self.provider.create() as workspace:
                        with reproduction_file(workspace.path, spec, source):
                            execution = self.runner.run(
                                workspace.path,
                                spec.command,
                                artifact_root=directory / "reproduction-baseline",
                            )
                        _write_json(
                            directory / "reproduction-baseline.json",
                            {
                                "result": asdict(execution.result),
                                "workspace": asdict(workspace.provenance),
                                "artifact_directory": execution.artifact_directory,
                            },
                        )
                except ValueError as exc:
                    raise WorkflowError(str(exc)) from exc
                if execution.result.status != ValidationStatus.FAIL:
                    raise WorkflowError(
                        "generated reproduction must fail on the original revision without infrastructure errors"
                    )
                reproduction = (spec, source)
                public_commands += (spec.command,)
            if self.regression_tests:
                baseline = []
                passing_ids = []
                # Every check starts from the same unpatched revision, without
                # filesystem state left by another baseline check.
                for index, test in enumerate(self.regression_tests):
                    with self.provider.create() as workspace:
                        execution = self.runner.run(
                            workspace.path,
                            test.command,
                            artifact_root=directory
                            / "regression-baseline"
                            / str(index),
                        )
                        baseline.append(
                            {
                                "test_id": test.test_id,
                                "command": asdict(test.command),
                                "result": asdict(execution.result),
                                "artifact_directory": execution.artifact_directory,
                                "workspace": asdict(workspace.provenance),
                            }
                        )
                    if execution.result.status == ValidationStatus.PASS:
                        passing_ids.append(test.test_id)
                _write_json(directory / "regression-baseline.json", baseline)
                if any(
                    item["result"]["status"]
                    not in {ValidationStatus.PASS, ValidationStatus.FAIL}
                    for item in baseline
                ):
                    raise WorkflowError(
                        "regression baseline has an infrastructure failure"
                    )
                prompt = render_regression_selection_prompt(
                    self.task.problem_statement, tuple(passing_ids)
                )
                (directory / "regression-selection.txt").write_text(
                    prompt + "\n", encoding="utf-8"
                )
                try:
                    excluded = parse_regression_exclusions(
                        responses.regression_exclusions, tuple(passing_ids)
                    )
                except ValueError as exc:
                    raise WorkflowError(str(exc)) from exc
                selected = tuple(
                    test
                    for test in self.regression_tests
                    if test.test_id in passing_ids and test.test_id not in excluded
                )
                public_commands = (
                    tuple(test.command for test in selected) + public_commands
                )
                _write_json(
                    directory / "regression-selection.json",
                    {
                        "passing_ids": passing_ids,
                        "excluded_ids": excluded,
                        "selected_ids": [test.test_id for test in selected],
                        "response": responses.regression_exclusions,
                    },
                )
                if not public_commands:
                    raise WorkflowError(
                        "regression selection left no public validation commands"
                    )
            _write_json(
                directory / "task.json",
                {
                    "benchmark": self.task.benchmark,
                    "benchmark_revision": self.task.benchmark_revision,
                    "instance_id": self.task.instance_id,
                    "language": self.task.language,
                    "repository_url": self.task.repository_url,
                    "base_commit": self.task.base_commit,
                    "problem_statement": self.task.problem_statement,
                    "container_image": self.task.container_image,
                    "container_digest": self.task.container_digest,
                    "timeout_seconds": self.task.timeout_seconds,
                    "memory_megabytes": self.task.memory_megabytes,
                    "visible_metadata": self.task.visible_metadata,
                },
            )
            _write_json(
                directory / "controller.json",
                {
                    "implementation_revision": self.implementation_revision,
                    "harness_revision": self.harness_revision,
                    "model_name": self.model_name,
                    "model_calls": 0,
                    "localization_mode": "edit-samples"
                    if responses.edit_samples
                    else "edit-lines"
                    if responses.edit_localization is not None or responses.edit_samples
                    else "symbols-only",
                    "resolved_container_digest": self.runner.image_id,
                    "public_commands": [asdict(command) for command in public_commands],
                },
            )
            with self.provider.create() as visible_workspace:
                repository_name = Path(self.provider.source_repository).name
                source_paths = tuple(
                    sorted(
                        path
                        for path in self.provider.paths
                        if self.adapter.is_source_path(path)
                    )
                )
                if not source_paths:
                    raise WorkflowError(
                        "pinned repository has no supported source files"
                    )
                project_tree = render_project_tree(
                    tuple(f"{repository_name}/{path}" for path in source_paths),
                    adapter=self.adapter,
                )
                file_prompt = render_file_localization_prompt(
                    self.task.problem_statement,
                    project_tree,
                    extension=self.adapter.extension,
                )
                selected_files = parse_file_locations(
                    responses.file_localization,
                    source_paths,
                    repository_name=repository_name,
                    extension=self.adapter.extensions,
                )
                if not selected_files:
                    raise WorkflowError(
                        "file localization selected no known source files"
                    )
                sources = {
                    path: (visible_workspace.path / path).read_text(encoding="utf-8")
                    for path in selected_files
                }
                nodes = {
                    path: self.adapter.parse_file(path, source)
                    for path, source in sources.items()
                }
                symbol_prompt = render_symbol_localization_prompt(
                    self.task.problem_statement,
                    sources,
                    adapter=self.adapter,
                )
                locations = parse_locations_for_files(
                    extract_code_blocks(responses.symbol_localization),
                    selected_files,
                    extension=self.adapter.extensions,
                )
                selected_context, intervals = construct_selected_context(
                    locations, nodes, sources
                )
                intervals = {
                    path: [(max(1, start), end) for start, end in spans]
                    for path, spans in intervals.items()
                }
                if not selected_context.strip():
                    raise WorkflowError(
                        "symbol localization produced no valid repair context"
                    )
                edit_prompt = None
                repair_plan = []
                if responses.edit_samples:
                    numbered_context, _ = construct_selected_context(
                        locations, nodes, sources, no_line_number=False
                    )
                    edit_prompt = render_edit_localization_prompt(
                        self.task.problem_statement, numbered_context
                    )
                    visible_intervals = {
                        path: [
                            (start, min(nodes[path].line_count, end))
                            for start, end in spans
                        ]
                        for path, spans in intervals.items()
                    }
                    _write_json(
                        directory / "symbol-context.json",
                        {
                            "locations": locations,
                            "intervals": visible_intervals,
                            "context": numbered_context,
                            "edit_prompt": edit_prompt,
                        },
                    )
                    for rank, sample in enumerate(responses.edit_samples):
                        sample_directory = directory / "localizations" / str(rank)
                        sample_directory.mkdir(parents=True)
                        try:
                            sample_locations = parse_edit_locations(
                                sample.edit_localization, visible_intervals
                            )
                        except ValueError as exc:
                            raise WorkflowError(f"edit sample {rank}: {exc}") from exc
                        context, sample_intervals = construct_selected_context(
                            sample_locations, nodes, sources
                        )
                        sample_intervals = {
                            path: [
                                (max(1, start), min(nodes[path].line_count, end))
                                for start, end in spans
                            ]
                            for path, spans in sample_intervals.items()
                        }
                        _write_json(
                            sample_directory / "selected-context.json",
                            {
                                "localization_rank": rank,
                                "locations": sample_locations,
                                "intervals": sample_intervals,
                                "context": context,
                            },
                        )
                        (sample_directory / "repair.txt").write_text(
                            build_repair_prompt(
                                self.task.problem_statement,
                                context,
                                language=self.adapter.language,
                            )
                            + "\n",
                            encoding="utf-8",
                        )
                        repair_plan.extend(
                            (rank, index, response, sample_intervals)
                            for index, response in enumerate(sample.repairs)
                        )
                if responses.edit_localization is not None:
                    numbered_context, _ = construct_selected_context(
                        locations, nodes, sources, no_line_number=False
                    )
                    edit_prompt = render_edit_localization_prompt(
                        self.task.problem_statement, numbered_context
                    )
                    # Retain the coarse evidence even when the fine response fails.
                    _write_json(
                        directory / "symbol-context.json",
                        {
                            "locations": locations,
                            "intervals": intervals,
                            "context": numbered_context,
                            "edit_prompt": edit_prompt,
                            "edit_response": responses.edit_localization,
                        },
                    )
                    try:
                        locations = parse_edit_locations(
                            responses.edit_localization,
                            {
                                path: [
                                    (start, min(nodes[path].line_count, end))
                                    for start, end in spans
                                ]
                                for path, spans in intervals.items()
                            },
                        )
                    except ValueError as exc:
                        raise WorkflowError(str(exc)) from exc
                    selected_context, intervals = construct_selected_context(
                        locations, nodes, sources
                    )
                    intervals = {
                        path: [
                            (max(1, start), min(nodes[path].line_count, end))
                            for start, end in spans
                        ]
                        for path, spans in intervals.items()
                    }
                repair_prompt = build_repair_prompt(
                    self.task.problem_statement,
                    selected_context,
                    language=self.adapter.language,
                )
                if not responses.edit_samples:
                    repair_plan = [
                        (0, index, response, intervals)
                        for index, response in enumerate(responses.repairs)
                    ]

            prompts = directory / "prompts"
            prompts.mkdir()
            if edit_prompt is not None:
                (prompts / "edit-localization.txt").write_text(
                    edit_prompt + "\n", encoding="utf-8"
                )
            for name, content in (
                ("file-localization.txt", file_prompt),
                ("symbol-localization.txt", symbol_prompt),
                ("repair.txt", repair_prompt),
            ):
                if responses.edit_samples and name == "repair.txt":
                    continue
                (prompts / name).write_text(content + "\n", encoding="utf-8")
            _write_json(directory / "responses.json", asdict(responses))
            _write_json(
                directory
                / (
                    "coarse-context.json"
                    if responses.edit_samples
                    else "selected-context.json"
                ),
                {
                    "files": selected_files,
                    "locations": locations,
                    "intervals": intervals,
                    "context": selected_context,
                },
            )

            attempts: list[CandidateAttempt] = []
            candidates: list[PatchCandidate] = []
            for rank, index, response, candidate_intervals in repair_plan:
                candidate_id = (
                    f"loc-{rank}-repair-{index}"
                    if responses.edit_samples
                    else f"repair-{index}"
                )
                try:
                    edits = parse_search_replace_edits(response)
                    applied = apply_search_replace_edits(
                        sources, edits, allowed_intervals=candidate_intervals
                    )
                    candidate = build_patch_candidate(
                        candidate_id=candidate_id,
                        raw_response=response,
                        diff=build_unified_diff(
                            applied.original_sources, applied.updated_sources
                        ),
                        localization_rank=rank,
                        sample_index=index,
                    )
                except (
                    EditApplicationError,
                    EditParseError,
                    UnicodeError,
                    ValueError,
                ) as exc:
                    attempts.append(
                        CandidateAttempt(
                            candidate_id,
                            index,
                            "repair_error",
                            str(exc)[:2000],
                            localization_rank=rank,
                        )
                    )
                    continue
                candidate = validate_candidate(
                    candidate,
                    self.provider,
                    self.runner,
                    public_commands,
                    artifact_root=directory / "executions" / candidate_id,
                    reproduction=reproduction,
                )
                candidates.append(candidate)
                attempts.append(
                    CandidateAttempt(
                        candidate_id,
                        index,
                        "validated",
                        candidate=candidate,
                        localization_rank=rank,
                    )
                )
            if not candidates:
                raise WorkflowError("no repair response produced a patch candidate")
            try:
                selection = select_candidate(candidates)
            except ValueError as exc:
                raise WorkflowError(str(exc)) from exc
            selected = selection.candidate
            prediction = FinalPrediction(
                instance_id=self.task.instance_id,
                model_patch=selected.diff,
                selected_candidate_id=selected.candidate_id,
                model_name=self.model_name,
            )
            final_digest = hashlib.sha256(selected.diff.encode("utf-8")).hexdigest()
            duration = time.monotonic() - started
            if not math.isfinite(duration):
                raise WorkflowError("run duration is not finite")
            record = RunRecord(
                run_id=run_id,
                condition="agentless-ml-recorded",
                instance_id=self.task.instance_id,
                started_at=started_at,
                implementation_revision=self.implementation_revision,
                benchmark_revision=self.task.benchmark_revision,
                harness_revision=self.harness_revision,
                container_digest=self.runner.image_id,
                model_name=self.model_name,
                model_calls=0,
                input_tokens=0,
                output_tokens=0,
                wall_time_seconds=duration,
                final_patch_sha256=final_digest,
            )
            _write_json(
                directory / "attempts.json", [asdict(attempt) for attempt in attempts]
            )
            _write_json(directory / "prediction.json", asdict(prediction))
            _write_json(directory / "run.json", asdict(record))
            _write_json(
                directory / "selection.json",
                {
                    "reason": selection.reason,
                    "vote_count": selection.vote_count,
                    "considered_candidate_ids": selection.considered_candidate_ids,
                    "selected_candidate_id": selected.candidate_id,
                },
            )
            return WorkflowResult(
                prediction,
                record,
                tuple(attempts),
                selected_files,
                selection.reason,
                str(directory),
            )
        except Exception as exc:
            _write_json(
                directory / "failure.json",
                {
                    "type": type(exc).__name__,
                    "message": str(exc),
                    "model_calls": 0,
                },
            )
            raise
