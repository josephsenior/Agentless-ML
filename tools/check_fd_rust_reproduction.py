"""Check Rust reproduction reporting on real pinned fd source, not the task solution."""

from __future__ import annotations

import argparse
import base64
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import subprocess

from agentless_ml.adapters.benchmarks import DeepSWEDataset, DeepSWEDatasetPin, pinned_load_options
from agentless_ml.repair import build_patch_candidate, build_unified_diff
from agentless_ml.validation import DockerTestRunner, ReproductionSpec, rust_reproduction_command
from agentless_ml.validation.reproduction import reproduction_file
from agentless_ml.workspace import LocalGitWorkspaceProvider, PatchApplicationStatus, verify_sealed_repository

ROOT = Path(__file__).resolve().parents[1]
TASK_ID = 'fd-deterministic-multi-key-sorting'
RUST_SOURCE = '''#[test]
fn buffered_output() {
    let root = tempfile::tempdir().expect("create public input directory");
    std::fs::write(root.path().join("z.txt"), b"z").expect("write input");
    std::fs::write(root.path().join("a.txt"), b"a").expect("write input");
    let result = std::process::Command::new(env!("CARGO_BIN_EXE_fd"))
        .current_dir(root.path())
        .args(["--color", "never", "--type", "f", "--max-buffer-time", "10000", "."])
        .output().expect("run candidate-built fd");
    assert!(result.status.success(), "fd failed: {:?}", result);
    let stdout = String::from_utf8(result.stdout).expect("UTF-8 public output");
    let paths: Vec<_> = stdout.lines().map(|line| line.trim_start_matches("./")).collect();
    assert_eq!(paths, vec!["a.txt", "z.txt"]);
}
'''


def run_check(output: Path, tasks_root: Path, repositories: Path) -> dict:
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    pin = json.loads((ROOT / 'experiments/deepswe/corpus_pin.json').read_bytes())
    dataset = DeepSWEDataset(tasks_root, DeepSWEDatasetPin(
        revision=pin['revision'], agent_files_sha256=pin['agent_files_sha256'], task_count=pin['task_count']))
    (task,) = dataset.load_tasks(task_ids=(TASK_ID,), **pinned_load_options(pin))
    source = repositories / TASK_ID
    verify_sealed_repository(source, task.base_commit)
    provider = LocalGitWorkspaceProvider(source, task.base_commit, output / 'workspaces')
    runner = DockerTestRunner(task.container_image, output / 'executions', memory_mb=4096,
                              cpus=1, tmpfs_mb=4096, pids_limit=2048, run_as_image_user=True)
    assert runner.image_id == task.container_digest
    spec = ReproductionSpec('tests/agentless_reproduction.rs', rust_reproduction_command(
        'tests/agentless_reproduction.rs', test_name='buffered_output', timeout_seconds=600))
    outcomes = []
    for label, expected in [('pinned-base', 'pass'), ('broken-buffer-control', 'fail')]:
        with provider.create() as workspace:
            application = None
            if label == 'broken-buffer-control':
                path = 'src/walk.rs'
                original = (workspace.path / path).read_text(encoding='utf-8')
                assert original.count('            self.buffer.sort();') == 1
                updated = original.replace('            self.buffer.sort();', '            self.buffer.clear();')
                diff = build_unified_diff({path: original}, {path: updated})
                candidate = build_patch_candidate(
                    candidate_id=label, raw_response='authored negative control, not a repair',
                    diff=diff, localization_rank=0, sample_index=0, language='rust')
                application = workspace.apply_candidate(candidate)
                assert application.status is PatchApplicationStatus.APPLIED
                (output / 'negative-control.patch').write_text(diff, encoding='utf-8')
            with reproduction_file(workspace.path, spec, RUST_SOURCE):
                execution = runner.run(workspace.path, spec.command, artifact_root=output / label)
            record = {
                'label': label, 'expected': expected, 'result': asdict(execution.result),
                'artifact_directory': execution.artifact_directory,
                'workspace': asdict(workspace.provenance),
                'application': asdict(application) if application else None,
            }
            # Save provenance even when an assertion below stops this diagnostic.
            (output / (label + '.json')).write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
            assert execution.result.status.value == expected, record
            report = Path(execution.artifact_directory) / 'report.json'
            raw = report.read_bytes()
            document = json.loads(raw)
            junit = base64.b64decode(document['rust_junit_base64'], validate=True)
            assert b'buffered_output' in junit
            outcomes.append({
                'label': label, 'status': execution.result.status.value,
                'duration_seconds': execution.result.duration_seconds,
                'artifact_directory': execution.artifact_directory,
                'report_sha256': hashlib.sha256(raw).hexdigest(),
            })
    verify_sealed_repository(source, task.base_commit)
    assert not list((output / 'workspaces').iterdir())
    assert not (source / spec.path).exists()
    revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, check=True,
                              capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(['git', 'status', '--porcelain'], cwd=ROOT, check=True,
                           capture_output=True, text=True).stdout.strip()
    summary = {
        'scope': 'real fd repository existing-public-behavior diagnostic, not a task solve or full controller run',
        'task_id': TASK_ID, 'base_commit': task.base_commit, 'container_digest': runner.image_id,
        'implementation_revision': revision + ('+dirty' if dirty else ''),
        'outcomes': outcomes, 'model_calls': 0, 'source_unchanged': True,
        'candidate_workspaces_cleaned': True,
        'baseline_eligible_for_generated_reproduction': False,
    }
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--tasks-root', type=Path, required=True)
    parser.add_argument('--repositories', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run_check(args.output, args.tasks_root, args.repositories), indent=2))
