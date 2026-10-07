"""Pinned package inputs and opt-in functional tool verification."""

import json
import os
from pathlib import Path

import pytest

from agentless_ml.validation import DockerTestRunner
from agentless_ml.validation.docker import PublicTestCommand
from agentless_ml.validation.reports import ReportFormat, TestReport

ROOT = Path(__file__).resolve().parents[1]


def test_riscv_package_archives_are_pinned_before_installation():
    manifest = json.loads((ROOT / "experiments/deepswe/pwntools/riscv-packages.json").read_text())
    recipe = (ROOT / "experiments/deepswe/pwntools/Dockerfile.riscv").read_text()
    assert manifest["architecture"] == "amd64"
    assert {item["name"] for item in manifest["packages"]} == {"binutils-riscv64-linux-gnu", "patchelf"}
    for item in manifest["packages"]:
        assert f'{item["name"]}={item["version"]}' in recipe
        assert item["sha256"] in recipe
    assert recipe.index("sha256sum --check --strict") < recipe.index("apt-get install")
    assert "--no-remove --no-install-recommends" in recipe
    assert recipe.rstrip().endswith("USER travis")


@pytest.mark.skipif(not os.environ.get("AGENTLESS_PWNTOOLS_RISCV_IMAGE"), reason="opt-in RISC-V and patchelf verification")
def test_riscv_and_patchelf_under_existing_isolation(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "test_tools_probe.py").write_text(r'''import json
import shutil
import subprocess
from pathlib import Path

def run(*args):
    return subprocess.run(args, check=True, capture_output=True).stdout

def test_versions_and_installed_hashes():
    manifest = json.loads(Path('/opt/pwntools-riscv/packages.json').read_text())
    for item in manifest['packages']:
        assert run('dpkg-query', '-W', '-f=${Version}', item['name']).decode() == item['version']
    def inventory(name):
        return dict(line.split('\t') for line in Path('/opt/pwntools-riscv/' + name).read_text().splitlines())
    before = inventory('packages-before.tsv')
    after = inventory('packages-after.tsv')
    assert all(after.get(name) == version for name, version in before.items())
    assert set(after) - set(before) == {item['name'] for item in manifest['packages']}
    run('sha256sum', '--check', '/opt/pwntools-riscv/binary-sha256.txt')
    run('sha256sum', '--check', '/opt/pwntools-msp430/binary-sha256.txt')

def test_riscv_assembly_linking_and_disassembly():
    Path('/tmp/riscv.s').write_text('.text\n.global _start\n_start: addi t0, zero, 42\n')
    run('riscv64-linux-gnu-as', '-march=rv64i', '-mabi=lp64', '/tmp/riscv.s', '-o', '/tmp/riscv.o')
    run('riscv64-linux-gnu-ld', '-e', '_start', '/tmp/riscv.o', '-o', '/tmp/riscv.elf')
    run('riscv64-linux-gnu-objcopy', '-O', 'binary', '-j', '.text', '/tmp/riscv.elf', '/tmp/riscv.bin')
    assert Path('/tmp/riscv.bin').read_bytes() == bytes.fromhex('9302a002')
    output = run('riscv64-linux-gnu-objdump', '-d', '/tmp/riscv.elf')
    assert b'li' in output and b't0,42' in output

def test_pwntools_riscv_assembly():
    from pwn import asm
    assert asm('addi t0, zero, 42', arch='riscv64') == bytes.fromhex('9302a002')

def test_patchelf_rewrites_and_runs_an_executable():
    Path('/tmp/probe.c').write_text('int main(void) { return 0; }')
    run('gcc', '/tmp/probe.c', '-o', '/tmp/probe')
    interpreter = run('patchelf', '--print-interpreter', '/tmp/probe').decode().strip()
    shutil.copyfile(interpreter, '/tmp/probe-loader')
    Path('/tmp/probe-loader').chmod(0o755)
    run('patchelf', '--set-interpreter', '/tmp/probe-loader', '--set-rpath', '/tmp/probe-lib', '/tmp/probe')
    assert run('patchelf', '--print-interpreter', '/tmp/probe').strip() == b'/tmp/probe-loader'
    assert run('patchelf', '--print-rpath', '/tmp/probe').strip() == b'/tmp/probe-lib'
    assert b'/tmp/probe-loader' in run('readelf', '-l', '/tmp/probe')
    assert b'/tmp/probe-lib' in run('readelf', '-d', '/tmp/probe')
    run('/tmp/probe')
''', encoding="utf-8")
    artifacts = Path(os.environ.get("AGENTLESS_PWNTOOLS_RISCV_ARTIFACTS", str(tmp_path / "logs")))
    runner = DockerTestRunner(os.environ["AGENTLESS_PWNTOOLS_RISCV_IMAGE"], artifacts,
                              memory_mb=8192, cpus=2, tmpfs_mb=4096,
                              pids_limit=2048, run_as_image_user=True)
    execution = runner.run(source, PublicTestCommand(
        ("sh", "-c", "cd /tmp/work && PWNLIB_NOTERM=1 python -m pytest -p no:cacheprovider --junitxml=/tmp/report.xml"),
        timeout_seconds=90, report=TestReport(ReportFormat.JUNIT_XML, "/tmp/report.xml"),
    ))
    assert execution.result.status.value == "pass", f"{execution.message}; {execution.artifact_directory}"
    assert len(execution.result.test_cases) == 4
