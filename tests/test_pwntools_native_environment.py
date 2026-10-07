"""The native diagnostic must work without weakening DockerTestRunner."""

import os
from pathlib import Path

import pytest

from agentless_ml.adapters.benchmarks import deepswe_test_command
from agentless_ml.validation import DockerTestRunner
from agentless_ml.validation.docker import PublicTestCommand
from agentless_ml.validation.reports import ReportFormat, TestReport


def test_native_runner_is_explicit_and_keeps_the_public_runner_unchanged():
    native = deepswe_test_command("pwntools-native-doctest", ("source/tubes/ssh.rst",))
    assert native.argv[4:] == ("source/tubes/ssh.rst",)
    assert '. /opt/pwntools-setup-local-ssh.sh' in native.argv[2]
    assert '"$@"' in native.argv[2]
    assert 'setup-local-ssh' not in deepswe_test_command("pwntools-doctest").argv[2]


@pytest.mark.parametrize("target", ("../ssh.rst", "source/../ssh.rst", "-Dexclude_patterns=gdb.rst", "tubes/ssh"))
def test_native_diagnostic_refuses_non_document_selectors(target):
    with pytest.raises(ValueError, match="source/.*file paths"):
        deepswe_test_command("pwntools-native-doctest", (target,))


def test_ssh_setup_is_ephemeral_key_only_and_loopback_only():
    setup = (Path(__file__).resolve().parents[1] / "experiments/deepswe/pwntools/setup-local-ssh.sh").read_text()
    for required in ("ListenAddress 127.0.0.1", "PasswordAuthentication no",
                     "PermitRootLogin no", "StrictHostKeyChecking yes", "AllowUsers travis",
                     "HostKey /tmp/pwntools-sshd/host_key", 'trap ', 'exit 125'):
        assert required in setup
    assert "sudo " not in setup and "chown " not in setup


def test_aligned_ssh_image_keeps_home_on_tmpfs_and_sets_public_creation_mask():
    root = Path(__file__).resolve().parents[1] / "experiments/deepswe/pwntools"
    setup = (root / "setup-local-ssh.sh").read_text()
    image = (root / "Dockerfile.ssh-aligned").read_text()
    assert 'getent passwd travis' in setup
    assert 'Subsystem sftp internal-sftp -u 0002' in setup
    assert 'IdentityFile $HOME/.ssh/id_ed25519' in setup
    assert 'chmod 600 "$task_ssh_user_home/.ssh/authorized_keys"' in setup
    assert 'usermod --home /home/travis travis' in image
    assert 'ln -s /tmp/pwntools-ssh-user /home/travis' in image
    assert 'COPY setup-local-ssh.sh /opt/pwntools-setup-local-ssh-native.sh' in image
    assert image.rstrip().endswith('USER travis')


@pytest.mark.skipif(not os.environ.get("AGENTLESS_PWNTOOLS_NATIVE_IMAGE"), reason="opt-in isolated native/SSH environment probe")
def test_native_tools_and_loopback_ssh_work_with_all_capabilities_dropped(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "test_native_probe.py").write_text('''import os
import subprocess
from pathlib import Path

def test_no_privilege_widening():
    assert os.getuid() != 0
    status = Path('/proc/self/status').read_text()
    assert next(line.split()[1] for line in status.splitlines() if line.startswith('CapEff:')) == '0000000000000000'

def test_native_tools_present():
    for executable in ('gdb', 'gdbserver', 'aarch64-linux-gnu-as', 'arm-linux-gnueabihf-as', 'mips-linux-gnu-as', 'powerpc-linux-gnu-as', 'qemu-arm-static'):
        subprocess.run([executable, '--version'], check=True, capture_output=True, timeout=5)
    result = subprocess.run(['gdb', '-batch', '-nx', '-ex', 'python import rpyc; print("gdb-rpyc-" + rpyc.__version__)'], check=True, capture_output=True, timeout=5)
    assert b'gdb-rpyc-6.0.2' in result.stdout

def test_openssh_loopback_login_and_writable_remote_home():
    result = subprocess.run(['ssh', '-oBatchMode=yes', '-oConnectTimeout=3', 'example.pwnme', 'id -un; touch "$HOME/agentless-native-probe"'], check=True, capture_output=True, timeout=10)
    assert result.stdout.strip() == b'travis'

def test_pwntools_loopback_transport():
    from pwn import ssh
    connection = ssh(host='example.pwnme', timeout=3)
    try:
        process = connection.run('printf agentless-loopback')
        assert process.recvall(timeout=3) == b'agentless-loopback'
    finally:
        connection.close()
''', encoding="utf-8")
    artifacts = Path(os.environ.get("AGENTLESS_PWNTOOLS_NATIVE_ARTIFACTS", str(tmp_path / "logs")))
    runner = DockerTestRunner(os.environ["AGENTLESS_PWNTOOLS_NATIVE_IMAGE"], artifacts,
                              memory_mb=8192, cpus=2, tmpfs_mb=4096,
                              pids_limit=2048, run_as_image_user=True)
    command = PublicTestCommand(
        ("sh", "-c", '. /opt/pwntools-setup-local-ssh.sh; cd /tmp/work; PWNLIB_NOTERM=1 python -m pytest -p no:cacheprovider --junitxml=/tmp/report.xml'),
        timeout_seconds=90, report=TestReport(ReportFormat.JUNIT_XML, "/tmp/report.xml"),
    )
    execution = runner.run(source, command)
    assert execution.result.status.value == "pass", f"{execution.message}; {execution.artifact_directory}"
    assert len(execution.result.test_cases) == 4


@pytest.mark.skipif(not os.environ.get("AGENTLESS_PWNTOOLS_ALIGNED_IMAGE"), reason="opt-in aligned SSH filesystem probe")
def test_aligned_home_and_creation_mask_without_changing_tmpfs(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "test_aligned_probe.py").write_text('''import os
import pwd
from pathlib import Path
from pwn import ssh, context
from pwnlib.filesystem import SSHPath

def test_aligned_environment():
    context.log_level = 'error'
    assert os.getuid() != 0
    assert pwd.getpwnam('travis').pw_dir == '/home/travis'
    assert os.environ['HOME'] == '/home/travis'
    assert Path('/home/travis').resolve() == Path('/tmp/pwntools-ssh-user')
    status = Path('/proc/self/status').read_text()
    assert next(line.split()[1] for line in status.splitlines() if line.startswith('CapEff:')) == '0000000000000000'
    assert next(line.split()[1] for line in status.splitlines() if line.startswith('NoNewPrivs:')) == '1'
    connection = ssh('travis', 'example.pwnme', timeout=3)
    try:
        connection.set_working_directory()
        file = SSHPath('created-file', ssh=connection)
        file.touch()
        assert file.stat().st_mode == 0o100664
        assert file.home.path == '/home/travis'
        assert SSHPath('~/my-file', ssh=connection).expanduser().path == '/home/travis/my-file'
        directory = SSHPath('a/b/c', ssh=connection)
        directory.mkdir(parents=True)
        process = connection.run(['ls', '-la', directory.absolute().path], env={'LC_ALL': 'C.UTF-8'})
        assert process.recvline(timeout=3) == b'total 0\\n'
        process.close()
        assert connection.run('stat -f -c %T .').recvall(timeout=3).strip() == b'tmpfs'
    finally:
        connection.close()
''', encoding="utf-8")
    artifacts = Path(os.environ.get("AGENTLESS_PWNTOOLS_NATIVE_ARTIFACTS", str(tmp_path / "logs")))
    runner = DockerTestRunner(os.environ["AGENTLESS_PWNTOOLS_ALIGNED_IMAGE"], artifacts,
                             memory_mb=8192, cpus=2, tmpfs_mb=4096,
                             pids_limit=2048, run_as_image_user=True)
    command = PublicTestCommand(
        ("sh", "-c", '. /opt/pwntools-setup-local-ssh.sh; cd /tmp/work; PWNLIB_NOTERM=1 python -m pytest -p no:cacheprovider --junitxml=/tmp/report.xml'),
        timeout_seconds=90, report=TestReport(ReportFormat.JUNIT_XML, "/tmp/report.xml"),
    )
    execution = runner.run(source, command)
    assert execution.result.status.value == "pass", f"{execution.message}; {execution.artifact_directory}"
    assert len(execution.result.test_cases) == 1
