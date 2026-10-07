"""Opt-in diagnosis of public libcdb data requirements; not regression passes."""

import os
from pathlib import Path

import pytest

from agentless_ml.validation import DockerTestRunner
from agentless_ml.validation.docker import PublicTestCommand
from agentless_ml.validation.reports import ReportFormat, TestReport
from agentless_ml.workspace import LocalGitWorkspaceProvider

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(not os.environ.get("AGENTLESS_PWNTOOLS_LIBCDB_IMAGE"), reason="opt-in offline libcdb diagnosis")
def test_libcdb_offline_reproductions(tmp_path):
    repositories = Path(os.environ.get("AGENTLESS_DELEGATED_TASK_REPOSITORIES", str(ROOT.parent / "benchmarks/deepswe/repos")))
    provider = LocalGitWorkspaceProvider(repositories / "pwntools-tube-multiplexing",
        "76894a5404a65d2800b6d0adaf3485ecba275caa", tmp_path / "workspaces")
    artifacts = Path(os.environ.get("AGENTLESS_PWNTOOLS_LIBCDB_ARTIFACTS", str(tmp_path / "logs")))
    runner = DockerTestRunner(os.environ["AGENTLESS_PWNTOOLS_LIBCDB_IMAGE"], artifacts,
        memory_mb=8192, cpus=2, tmpfs_mb=4096, pids_limit=2048, run_as_image_user=True)
    with provider.create() as workspace:
        (workspace.path / "agentless_libcdb_probe.py").write_text(r'''import hashlib
import importlib
import json
import re
import shutil
from pathlib import Path

import pytest
from pwn import ELF, context
import pwnlib.libcdb as libcdb

def record(name, **facts):
    print('LIBCDB_DIAGNOSTIC ' + json.dumps(dict(probe=name, **facts), sort_keys=True))

@pytest.fixture(autouse=True)
def fresh_lookup_state(tmp_path):
    # Restore module-owned provider lists between authored diagnostic cases.
    importlib.reload(libcdb)
    cache = tmp_path / 'cache'
    cache.mkdir()
    with context.local(cache_dir=str(cache)):
        yield

def system_libc():
    return ELF('/bin/sh', checksec=False).libc

def test_system_lookup_works_without_database_or_network():
    local = system_libc()
    buildid = local.buildid.hex()
    found = libcdb.search_by_build_id(buildid, unstrip=False, offline_only=True)
    assert found and Path(found).read_bytes() == local.data
    source = Path(libcdb.__file__).read_text()
    requests = sorted(set(re.findall(r"search_by_(hash|build_id|md5|sha1|sha256|libs_id)\('([^']+)'", source)))
    widths = {'hash': 40, 'build_id': 40, 'md5': 32, 'sha1': 40, 'sha256': 64}
    short_ids = [dict(kind=kind, value=value, length=len(value), expected_width=widths[kind])
                 for kind, value in requests if kind in widths and value != 'XX' and len(value) < widths[kind]]
    database = Path(context.local_libcdb)
    record('inventory-and-local-control', system_libc=local.path,
           system_build_id=buildid, system_sha256=hashlib.sha256(local.data).hexdigest(),
           local_database=str(database), database_exists=database.is_dir(),
           eu_unstrip=shutil.which('eu-unstrip'), literal_public_requests=requests,
           shorter_than_usual_hash_width=short_ids,
           local_offline_lookup_passed=True)
    assert not database.is_dir()
    assert shutil.which('eu-unstrip') is None

def test_missing_public_build_id_creates_negative_cache():
    buildid = '2d1c5e0b85cb06ff47fa6fa088ec22cb6e06074e'
    assert libcdb.search_by_build_id(buildid, unstrip=False, offline_only=True) is None
    cache = Path(context.cache_dir) / 'libcdb/build_id' / buildid
    assert cache.is_file() and cache.stat().st_size == 0
    cached_path, valid = libcdb._check_elf_cache('libcdb', buildid, 'build_id')
    assert cached_path is None and valid is False
    record('missing-public-id', build_id=buildid, result=None,
           negative_cache_bytes=cache.stat().st_size,
           retry_expiry_seconds=libcdb.NEGATIVE_CACHE_EXPIRY,
           original_offline_providers=[provider.__name__ for provider in libcdb.PROVIDERS['offline']])

def test_local_database_lookup_with_existing_library(tmp_path):
    local = system_libc()
    database = tmp_path / 'authored-db'
    database.mkdir()
    (database / 'author-control.so').write_bytes(local.data)
    with context.local(local_libcdb=str(database)):
        raw = libcdb.provider_local_database(local.buildid.hex(), 'build_id')
        found = libcdb.search_by_libs_id('author-control', unstrip=False, offline_only=True)
        assert raw == local.data and found and Path(found).read_bytes() == local.data
    record('authored-local-db-control', matched_existing_system_bytes=True,
           lookup_by_build_id_and_libs_id_passed=True,
           public_historical_data_added=False)

def test_matching_package_is_not_available_offline():
    local = system_libc()
    result = libcdb.download_libraries(local.path, unstrip=False)
    record('matching-library-package', system_build_id=local.buildid.hex(),
           result=result, unstrip_requested=False, network_enabled=False)
    assert result is None

def test_default_lookup_mutates_offline_provider_list():
    before = [provider.__name__ for provider in libcdb.PROVIDERS['offline']]
    local = system_libc()
    # This succeeds locally: the provider-list mutation occurs before the
    # first provider match, without an actual online request being needed.
    found = libcdb.search_by_build_id(local.buildid.hex(), unstrip=False)
    after = [provider.__name__ for provider in libcdb.PROVIDERS['offline']]
    assert found and before == ['provider_local_system', 'provider_local_database']
    assert after == before + [provider.__name__ for provider in libcdb.PROVIDERS['online']]
    record('provider-list-aliasing', before=before, after=after,
           successful_local_default_lookup=True,
           offline_only_not_a_sufficient_network_guard_after_default_lookup=True)
''', encoding="utf-8")
        execution = runner.run(workspace.path, PublicTestCommand(
            ("sh", "-c", "cd /tmp/work && PYTHONPATH=/tmp/work PWNLIB_NOTERM=1 python -m pytest -s -q -p no:cacheprovider agentless_libcdb_probe.py --junitxml=/tmp/report.xml"),
            timeout_seconds=120, report=TestReport(ReportFormat.JUNIT_XML, "/tmp/report.xml"),
        ))
    assert execution.result.status.value == "pass", f"{execution.message}; {execution.artifact_directory}"
    assert len(execution.result.test_cases) == 5
