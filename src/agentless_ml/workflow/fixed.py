"""One fixed localization, repair, public-validation, and selection trajectory."""

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

from agentless_ml.adapters.languages import PythonAdapter
from agentless_ml.localization import (
    construct_selected_context,
    extract_code_blocks,
    parse_file_locations,
    parse_locations_for_files,
    render_file_localization_prompt,
    render_legacy_project_tree,
    render_symbol_localization_prompt,
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
from agentless_ml.schemas import FinalPrediction, PatchCandidate, RunRecord, TaskSpec
from agentless_ml.validation import (
    DockerTestRunner,
    PublicTestCommand,
    validate_candidate,
)
from agentless_ml.workspace import LocalGitWorkspaceProvider


class WorkflowError(RuntimeError):
    """A recorded fixed trajectory cannot produce an auditable prediction."""


@dataclass(frozen=True, slots=True)
class RecordedStageResponses:
    file_localization: str
    symbol_localization: str
    repairs: tuple[str, ...]
    source: str = "recorded"

    def __post_init__(self):
        if not self.file_localization.strip() or not self.symbol_localization.strip():
            raise ValueError("localization responses must not be empty")
        if not self.repairs or any(not response.strip() for response in self.repairs):
            raise ValueError("at least one nonempty repair response is required")
        if not self.source.strip():
            raise ValueError("response source must not be empty")


@dataclass(frozen=True, slots=True)
class CandidateAttempt:
    candidate_id: str
    sample_index: int
    status: str
    message: str = ""
    candidate: PatchCandidate | None = None


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
    ):
        if task.language.casefold() != "python":
            raise ValueError("the first complete workflow supports Python only")
        if not public_commands:
            raise ValueError("public test schedule must not be empty")
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
        self.implementation_revision = implementation_revision
        self.harness_revision = harness_revision
        self.model_name = model_name

    def run(self, responses: RecordedStageResponses) -> WorkflowResult:
        started_at = datetime.now(UTC)
        started = time.monotonic()
        run_id = "run-" + uuid.uuid4().hex
        directory = self.artifact_root / run_id
        directory.mkdir(parents=True)
        try:
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
                    "resolved_container_digest": self.runner.image_id,
                    "public_commands": [
                        asdict(command) for command in self.public_commands
                    ],
                },
            )
            with self.provider.create() as visible_workspace:
                repository_name = Path(self.provider.source_repository).name
                python_paths = tuple(
                    sorted(path for path in self.provider.paths if path.endswith(".py"))
                )
                if not python_paths:
                    raise WorkflowError("pinned repository has no tracked Python files")
                project_tree = render_legacy_project_tree(
                    tuple(f"{repository_name}/{path}" for path in python_paths)
                )
                file_prompt = render_file_localization_prompt(
                    self.task.problem_statement, project_tree
                )
                selected_files = parse_file_locations(
                    responses.file_localization,
                    python_paths,
                    repository_name=repository_name,
                )
                if not selected_files:
                    raise WorkflowError(
                        "file localization selected no known Python files"
                    )
                sources = {
                    path: (visible_workspace.path / path).read_text(encoding="utf-8")
                    for path in selected_files
                }
                nodes = {
                    path: PythonAdapter().parse_file(path, source)
                    for path, source in sources.items()
                }
                symbol_prompt = render_symbol_localization_prompt(
                    self.task.problem_statement, sources
                )
                locations = parse_locations_for_files(
                    extract_code_blocks(responses.symbol_localization), selected_files
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
                repair_prompt = build_repair_prompt(
                    self.task.problem_statement, selected_context
                )

            prompts = directory / "prompts"
            prompts.mkdir()
            for name, content in (
                ("file-localization.txt", file_prompt),
                ("symbol-localization.txt", symbol_prompt),
                ("repair.txt", repair_prompt),
            ):
                (prompts / name).write_text(content + "\n", encoding="utf-8")
            _write_json(directory / "responses.json", asdict(responses))
            _write_json(
                directory / "selected-context.json",
                {
                    "files": selected_files,
                    "locations": locations,
                    "intervals": intervals,
                    "context": selected_context,
                },
            )

            attempts: list[CandidateAttempt] = []
            candidates: list[PatchCandidate] = []
            for index, response in enumerate(responses.repairs):
                candidate_id = f"repair-{index}"
                try:
                    edits = parse_search_replace_edits(response)
                    applied = apply_search_replace_edits(
                        sources, edits, allowed_intervals=intervals
                    )
                    candidate = build_patch_candidate(
                        candidate_id=candidate_id,
                        raw_response=response,
                        diff=build_unified_diff(
                            applied.original_sources, applied.updated_sources
                        ),
                        localization_rank=0,
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
                            candidate_id, index, "repair_error", str(exc)[:2000]
                        )
                    )
                    continue
                candidate = validate_candidate(
                    candidate,
                    self.provider,
                    self.runner,
                    self.public_commands,
                    artifact_root=directory / "executions" / candidate_id,
                )
                candidates.append(candidate)
                attempts.append(
                    CandidateAttempt(
                        candidate_id, index, "validated", candidate=candidate
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
