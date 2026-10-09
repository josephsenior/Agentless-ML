"""Explicit, verified runtime registrations; never overwrite published task pins.

The only supported profile is Testem's four-file loopback service. A registry
entry cannot inject shell commands, hostname mappings, resource changes or
arbitrary evidence paths. Explicit --image diagnostics bypass registrations.
"""

import json
import re
from dataclasses import replace
from pathlib import Path

from agentless_ml.validation import DockerTestRunner
from run_testem_qunit_public_test import OfflineAssetRunner, SUPERVISOR

REGISTRY = Path(__file__).resolve().parents[1] / 'experiments/deepswe/environments.json'
TASK = 'testem-per-launcher-reports'
CONDITION = 'modified environment: offline public-asset delivery'
KEYS = {'profile', 'condition', 'base_commit', 'published_image_id',
        'image', 'image_id', 'verification', 'reason'}


def load_environments(path=REGISTRY):
    path = Path(path)
    entries = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(entries, dict):
        raise ValueError('Environment registry must be an object')
    for task_id, entry in entries.items():
        if (task_id != TASK or not isinstance(entry, dict) or set(entry) != KEYS
                or entry['profile'] != 'testem-offline-qunit-v1'
                or entry['condition'] != CONDITION):
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
        if entry['verification'] != 'testem_qunit_todo_full_schedule_2026_10_10.json':
            raise ValueError('Requires the reviewed full-schedule evidence filename')
        evidence = json.loads((path.parent / entry['verification']).read_text(encoding='utf-8'))
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


def environment_for(task, entries):
    entry = entries.get(task.instance_id)
    if entry is not None and (task.base_commit != entry['base_commit']
                             or task.container_digest != entry['published_image_id']):
        raise ValueError('Environment registration does not match the published task pins')
    return entry


def runtime_task(task, environment):
    if environment is None:
        return task
    return replace(task, container_image=environment['image'], container_digest=environment['image_id'])


def runtime_command(command, environment):
    if environment is None:
        return command
    # Keep caller-provided targets, report, timeout and failure codes intact.
    # As with the verified full run, only the writable HOME prefix and owned
    # public-file service surround the original Mocha command.
    if command.argv[:2] != ('sh', '-c'):
        raise ValueError('Testem environment requires its shell-based public command')
    inner = (command.argv[0], command.argv[1],
        'mkdir -p /tmp/testem-firefox-home && export HOME=/tmp/testem-firefox-home && ' + command.argv[2],
        *command.argv[3:])
    return replace(command, argv=('python3', '-c', SUPERVISOR.replace('PUBLIC_TEST_ARGV', repr(list(inner)))))


def runtime_runner(image, artifacts, environment, **limits):
    runner_type = OfflineAssetRunner if environment is not None else DockerTestRunner
    runner = runner_type(image, artifacts, **limits)
    if environment is not None and runner.image_id != environment['image_id']:
        raise ValueError('Registered runtime image does not match its verified immutable ID')
    return runner
