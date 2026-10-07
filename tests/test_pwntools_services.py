"""The service condition is explicit, hash-checked and uses real transport."""

import hashlib
import importlib.util
import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def module(path):
    spec = importlib.util.spec_from_file_location('pwntools_service_test_module', ROOT / path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


@pytest.fixture
def snapshots(tmp_path):
    records = []
    for filename, data in [('pypi.json', b'{"versions": ["1.0.0"]}'), ('robots.txt', b'public fixture')]:
        (tmp_path / filename).write_bytes(data)
        records.append({'file': filename, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
    (tmp_path / 'manifest.json').write_text(json.dumps({'snapshots': records}))
    return tmp_path


def test_verified_snapshots_are_loaded(snapshots):
    service = module('experiments/deepswe/pwntools/offline-services.py')
    assert service.load_snapshots(snapshots)['pypi.json'] == b'{"versions": ["1.0.0"]}'


@pytest.mark.parametrize('mutation', ['tamper', 'missing', 'extra', 'invalid_versions'])
def test_invalid_snapshots_stop_the_service(snapshots, mutation):
    service = module('experiments/deepswe/pwntools/offline-services.py')
    if mutation == 'tamper':
        (snapshots / 'robots.txt').write_bytes(b'changed')
    elif mutation == 'missing':
        (snapshots / 'robots.txt').unlink()
    else:
        manifest = json.loads((snapshots / 'manifest.json').read_text())
        if mutation == 'extra':
            manifest['snapshots'].append({'file': '../unexpected'})
        else:
            data = b'{"versions": []}'
            (snapshots / 'pypi.json').write_bytes(data)
            manifest['snapshots'][0].update(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        (snapshots / 'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises((ValueError, FileNotFoundError)):
        service.load_snapshots(snapshots)


def test_only_explicit_service_runner_adds_exact_loopback_hosts(monkeypatch):
    tool = module('tools/run_pwntools_service_tests.py')
    calls = []
    monkeypatch.setattr(tool.DockerTestRunner, '_docker', staticmethod(lambda *args, **kw: calls.append((args, kw))))
    tool.OfflineServiceRunner._docker('create', '--network=none', 'image')
    assert calls[0][0] == ('create', '--add-host=pypi.org:127.0.0.1',
                          '--add-host=httpbingo.org:127.0.0.1', '--network=none', 'image')
    tool.OfflineServiceRunner._docker('exec', 'container', 'command')
    assert calls[1][0] == ('exec', 'container', 'command')


def test_service_bootstrap_never_seeds_update_or_disables_tls():
    root = ROOT / 'experiments/deepswe/pwntools'
    service = (root / 'offline-services.py').read_text()
    setup = (root / 'setup-offline-services.sh').read_text()
    assert 'available_on_pypi' not in service + setup
    assert 'verify=False' not in service.replace('# Removing explicit trust must fail; never use verify=False.', '')
    assert 'verify=requests.certs.where()' in service
    assert 'export REQUESTS_CA_BUNDLE=' in setup
    assert 'exit 125' in setup and 'trap ' in setup
    assert "('127.0.0.1', 443)" in service
    assert 'TLSVersion.TLSv1_2' in service


def test_reviewed_capture_pins_cannot_be_silently_replaced():
    tool = module('tools/build_pwntools_service_image.py')
    records = json.loads((ROOT / 'experiments/deepswe/pwntools/service-snapshots.json').read_text())['snapshots']
    tool.verify_pins(records)
    records[0]['sha256'] = '0' * 64
    with pytest.raises(ValueError, match='reviewed snapshot'):
        tool.verify_pins(records)


@pytest.mark.skipif(not os.environ.get('AGENTLESS_PWNTOOLS_SERVICE_IMAGE'), reason='opt-in real offline HTTPS and negative controls')
def test_real_offline_services_and_negative_controls(tmp_path):
    from agentless_ml.validation.docker import PublicTestCommand
    from agentless_ml.validation.reports import ReportFormat, TestReport
    tool = module('tools/run_pwntools_service_tests.py')
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'test_transport.py').write_text('''import json, os, signal, time
from pathlib import Path
import pytest, requests
import pwnlib.update as update
from pwnlib.util.web import wget

def test_real_transport_and_failure_controls():
    assert os.getuid() != 0
    status = Path('/proc/self/status').read_text()
    assert next(line.split()[1] for line in status.splitlines() if line.startswith('CapEff:')) == '0000000000000000'
    assert next(line.split()[1] for line in status.splitlines() if line.startswith('NoNewPrivs:')) == '1'
    assert getattr(update.available_on_pypi, 'cached', None) is None
    update.available_on_pypi()
    assert update.available_on_pypi.cached == json.loads(Path('/opt/pwntools-services/pypi.json').read_bytes())['versions']
    body = Path('/opt/pwntools-services/robots.txt').read_bytes()
    assert wget('https://httpbingo.org/robots.txt', timeout=3) == body
    assert wget('https://httpbingo.org/robots.txt', save='/tmp/download-control', timeout=3) == body
    assert Path('/tmp/download-control').read_bytes() == body
    with pytest.raises(requests.exceptions.SSLError):
        requests.get('https://httpbingo.org/robots.txt', verify=requests.certs.where(), timeout=3)
    with pytest.raises(requests.exceptions.SSLError):
        requests.get('https://127.0.0.1/robots.txt', verify=os.environ['REQUESTS_CA_BUNDLE'], timeout=3)
    assert requests.get('https://httpbingo.org/unsupported', timeout=3).status_code == 404
    os.kill(int(os.environ['PWNTOOLS_SERVICE_PID']), signal.SIGTERM)
    time.sleep(0.1)
    del update.available_on_pypi.cached
    with pytest.raises(requests.exceptions.ConnectionError):
        update.available_on_pypi()
''', encoding='utf-8')
    runner = tool.OfflineServiceRunner(os.environ['AGENTLESS_PWNTOOLS_SERVICE_IMAGE'],
        Path(os.environ.get('AGENTLESS_PWNTOOLS_SERVICE_ARTIFACTS', str(tmp_path / 'logs'))),
        memory_mb=8192, cpus=2, tmpfs_mb=4096, pids_limit=2048, run_as_image_user=True)
    command = PublicTestCommand(('sh', '-c',
        '. /opt/pwntools-setup-local-ssh.sh; export PWNTOOLS_SERVICE_PID="$task_service_pid"; cd /tmp/work; python -m pytest -p no:cacheprovider --junitxml=/tmp/report.xml'),
        timeout_seconds=60, report=TestReport(ReportFormat.JUNIT_XML, '/tmp/report.xml'))
    execution = runner.run(source, command)
    assert execution.result.status.value == 'pass', f'{execution.message}; {execution.artifact_directory}'
