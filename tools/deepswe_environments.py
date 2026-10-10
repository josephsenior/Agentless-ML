"""Explicit, verified runtime registrations; never overwrite published task pins.

Profiles cover Testem's public-file service, Cliffy's cache supplement and
GoReleaser's cache relocation/seeding.
A registry entry cannot inject shell commands, hostname mappings, resource
changes or arbitrary evidence paths. Explicit --image diagnostics bypass registrations.
"""

import hashlib
import json
import re
from dataclasses import replace
from pathlib import Path

from agentless_ml.validation import DockerTestRunner
from agentless_ml.validation.docker import DockerError, _snapshot
from agentless_ml.validation.helm_fixtures import (
    BASE as HELM_BASE, IMAGES as HELM_IMAGES,
    SPECIAL_LINKS as HELM_SPECIAL_LINKS, CONTAINER_SETUP as HELM_SETUP,
)
from run_testem_qunit_public_test import OfflineAssetRunner, SUPERVISOR
from run_goreleaser_cache_diagnostic import cache_command

REGISTRY = Path(__file__).resolve().parents[1] / 'experiments/deepswe/environments.json'
TASK = 'testem-per-launcher-reports'
CONDITION = 'modified environment: offline public-asset delivery'
CLIFFY = 'cliffy-config-file-parsing'
GORELEASER = 'goreleaser-retry-publish-auditing'
PROFILES = {
    TASK: ('testem-offline-qunit-v1', CONDITION, 'testem_qunit_todo_full_schedule_2026_10_10.json'),
    CLIFFY: ('cliffy-verified-cache-v1', 'modified environment: verified offline dependency cache',
             'cliffy_public_baseline_2026_10_09.json'),
    GORELEASER: ('goreleaser-relocated-cache-v1', 'modified environment: relocated Go caches with writable build seed',
                'goreleaser_cache_2026_10_08.json'),
}
KEYS = {'profile', 'condition', 'base_commit', 'published_image_id',
        'image', 'image_id', 'verification', 'reason'}


def load_environments(path=REGISTRY):
    path = Path(path)
    entries = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(entries, dict):
        raise ValueError('Environment registry must be an object')
    for task_id, entry in entries.items():
        if (task_id not in PROFILES or not isinstance(entry, dict) or set(entry) != KEYS
                or (entry['profile'], entry['condition'], entry['verification']) != PROFILES[task_id]):
            raise ValueError('Unknown task, environment profile or registry fields')
        if not isinstance(entry['reason'], str) or not entry['reason'].strip():
            raise ValueError('Registered environments need a reason')
        for key in ('image_id', 'published_image_id'):
            if not isinstance(entry[key], str) or not re.fullmatch(r'sha256:[0-9a-f]{64}', entry[key]):
                raise ValueError('Registered image IDs must be immutable SHA-256 pins')
        if entry['image'] != entry['image_id']:
            raise ValueError('Registered image reference must be its immutable ID')
        if not isinstance(entry['base_commit'], str) or not re.fullmatch(r'[0-9a-f]{40}', entry['base_commit']):
            raise ValueError('Registered base must be a full commit')
        evidence = json.loads((path.parent / entry['verification']).read_text(encoding='utf-8'))
        if task_id == CLIFFY:
            _verify_cliffy(entry, evidence, path.parent)
            continue
        if task_id == GORELEASER:
            _verify_goreleaser(entry, evidence)
            continue
        result = evidence['result']
        if (result['image_id'] != entry['image_id'] or result['base_commit'] != entry['base_commit']
                or result['condition'] != CONDITION or result['status'] != 'pass'
                or result['exit_code'] != 0 or not result['full_suite_run']
                or result['public_test_filter'] is not None
                or result['public_test_source_modified'] or result['browser_arguments_modified']
                or result['diagnostic_prototype_observer']
                or result['counts'].get('passed', 0) < 1):
            raise ValueError('Registration requires the passing unchanged full schedule in this exact image')
    return entries


def _verify_cliffy(entry, evidence, directory):
    graph = json.loads((directory / 'cliffy_offline_graph_2026_10_09.json').read_text(encoding='utf-8'))
    manifest = directory / 'cliffy/public_dependencies_2026_10_09.json'
    if (evidence['task_id'] != CLIFFY or evidence['image_id'] != entry['image_id']
            or evidence['base_commit'] != entry['base_commit']
            or evidence['condition'] != 'full_public_schedule_substituted_cache_environment'
            or evidence['status'] != 'pass' or evidence['exit_code'] != 0
            or evidence['normalized_regression_ids_passed'] < 1
            or evidence['failed'] != 0 or evidence['network'] != 'none'
            or not evidence['root_read_only'] or evidence['deno_version'] != '2.0.0'
            or graph['image_id'] != entry['image_id'] or graph['base_commit'] != entry['base_commit']
            or graph['parent_image_id'] != entry['published_image_id']
            or graph['status'] != 'pass' or graph['exit_code'] != 0
            or not graph['compile_time_import_graph_verified']
            or graph['manifest_sha256_at_build'] != hashlib.sha256(manifest.read_bytes()).hexdigest()):
        raise ValueError('Cliffy registration requires matching verified cache, graph and full passing evidence')


def environment_for(task, entries):
    entry = entries.get(task.instance_id)
    if entry is not None and (task.base_commit != entry['base_commit']
                             or task.container_digest != entry['published_image_id']):
        raise ValueError('Environment registration does not match the published task pins')
    return entry


def _verify_goreleaser(entry, evidence):
    result = evidence['full_attempt']
    # Readiness needs a usable passing inventory, not an all-green baseline.
    # Preserve the recorded FAIL/exit 1 and all failed/skipped cases as such.
    if (evidence['task_id'] != GORELEASER or evidence['image_id'] != entry['image_id']
            or evidence['parent_image_id'] != entry['published_image_id']
            or evidence['base_commit'] != entry['base_commit']
            or evidence['condition'] != 'substituted_environment_cache_relocation_diagnostic'
            or evidence['runner'] != 'go' or evidence['targets'] != ['./...']
            or evidence['module_check']['status'] != 'pass'
            or (result['status'], result['exit_code']) not in (('pass', 0), ('fail', 1))
            or result['passed'] < 1 or result['failed'] < 0 or result['skipped'] < 0
            or result['report_ids'] != result['passed'] + result['failed'] + result['skipped']
            or evidence['network'] != 'none' or not evidence['root_read_only']
            or evidence['memory_mb'] != 8192 or evidence['cpus'] != 2
            or evidence['tmpfs_mb'] != 4096 or evidence['pids_limit'] != 2048
            or evidence['timeout_seconds'] != 1800 or evidence['automatic_retry']):
        raise ValueError('GoReleaser registration requires the matching completed report-bearing baseline and module check')


def runtime_task(task, environment):
    if environment is None:
        return task
    return replace(task, container_image=environment['image'], container_digest=environment['image_id'])


def runtime_command(command, environment):
    if environment is None or environment['profile'] == 'cliffy-verified-cache-v1':
        return command
    if environment['profile'] == 'goreleaser-relocated-cache-v1':
        return cache_command(command)
    # Keep caller-provided targets, report, timeout and failure codes intact.
    # As with the verified full run, only the writable HOME prefix and owned
    # public-file service surround the original Mocha command.
    if command.argv[:2] != ('sh', '-c'):
        raise ValueError('Testem environment requires its shell-based public command')
    inner = (command.argv[0], command.argv[1],
        'mkdir -p /tmp/testem-firefox-home && export HOME=/tmp/testem-firefox-home && ' + command.argv[2],
        *command.argv[3:])
    return replace(command, argv=('python3', '-c', SUPERVISOR.replace('PUBLIC_TEST_ARGV', repr(list(inner)))))


class RegisteredImageRunner(DockerTestRunner):
    """Observe protections for an image-only registration; change no Docker args."""

    def __init__(self, *args, **kwargs):
        self.observed_host_config = None
        super().__init__(*args, **kwargs)

    def _docker(self, *args, **kwargs):
        result = DockerTestRunner._docker(*args, **kwargs)
        if args and args[0] == 'inspect':
            self.observed_host_config = json.loads(result.stdout)[0]['HostConfig']
        return result


class HelmFixtureRunner(RegisteredImageRunner):
    """Defer four exact Helm links, then recreate them only inside pinned Docker."""

    def __init__(self, image, artifacts, *, task, **limits):
        if (task.instance_id not in HELM_IMAGES or task.base_commit != HELM_BASE
                or task.container_digest != HELM_IMAGES[task.instance_id]):
            raise ValueError("Helm fixture setup requires the exact task, base and image pins")
        self.workspace_setup = None
        super().__init__(image, artifacts, **limits)
        if self.image_id != HELM_IMAGES[task.instance_id]:
            raise ValueError("Helm fixture setup requires its task's original pinned image")

    def _snapshot_source(self, source, target):
        self.workspace_setup = None
        _snapshot(source, target, _defer_helm_fixtures=True)

    def _prepare_workspace(self, container_name):
        self.workspace_setup = None
        result = self._docker("exec", container_name, "python", "-c", HELM_SETUP, timeout=30)
        try:
            record = json.loads(result.stdout)
        except (ValueError, UnicodeError) as error:
            raise DockerError("invalid Helm container fixture verification output") from error
        if record != {"profile": "helm-container-fixtures-v1", "links": HELM_SPECIAL_LINKS}:
            raise DockerError("Helm container fixture verification did not match the fixed policy")
        self.workspace_setup = record


def runtime_runner(image, artifacts, environment, *, task=None, **limits):
    if task is not None and task.instance_id in HELM_IMAGES:
        if environment is not None:
            raise ValueError("Helm fixture setup cannot be combined with a substituted environment")
        return HelmFixtureRunner(image, artifacts, task=task, **limits)
    runner_type = DockerTestRunner
    if environment is not None:
        runner_type = OfflineAssetRunner if environment['profile'] == 'testem-offline-qunit-v1' else RegisteredImageRunner
    runner = runner_type(image, artifacts, **limits)
    if environment is not None and runner.image_id != environment['image_id']:
        raise ValueError('Registered runtime image does not match its verified immutable ID')
    return runner
