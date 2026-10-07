"""Verification of the source-built toolchain and explicit public schedule."""

import importlib.util
import json
import os
from pathlib import Path

import pytest

from agentless_ml.validation import DockerTestRunner
from agentless_ml.validation.docker import PublicTestCommand
from agentless_ml.validation.reports import ReportFormat, TestReport

ROOT = Path(__file__).resolve().parents[1]


def test_archive_checksum_is_pinned_before_extraction():
    manifest = json.loads((ROOT / "experiments/deepswe/pwntools/msp430-source.json").read_text())
    recipe = (ROOT / "experiments/deepswe/pwntools/Dockerfile.msp430").read_text()
    assert manifest["archive_sha256"] == "0f8a4c272d7f17f369ded10a4aca28b8e304828e95526da482b0ccc4dfc9d8e1"
    assert manifest["archive_sha256"] in recipe
    assert recipe.index("sha256sum --check --strict") < recipe.index("tar -xf")
    assert "--target=msp430-elf" in recipe
    assert "COPY --from=msp430-build" in recipe


def test_public_docker_exclusions_change_only_the_three_temporary_pages(tmp_path):
    spec = importlib.util.spec_from_file_location("pwntools_native_tool", ROOT / "tools/run_pwntools_native_tests.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = tmp_path / "docs/source"
    source.mkdir(parents=True)
    for name in ("gdb.rst", "adb.rst", "protocols.rst", "asm.rst", "index.rst"):
        (source / name).write_text("original content", encoding="utf-8")
    module.apply_public_docker_schedule(tmp_path)
    assert module.PUBLIC_DOCKER_EXCLUSIONS == ("gdb.rst", "adb.rst", "protocols.rst")
    for name in module.PUBLIC_DOCKER_EXCLUSIONS:
        assert (source / name).read_text() == ""
    assert (source / "asm.rst").read_text() == "original content"
    assert (source / "index.rst").read_text() == "original content"


@pytest.mark.skipif(not os.environ.get("AGENTLESS_PWNTOOLS_MSP430_IMAGE"), reason="opt-in verified MSP430 toolchain probe")
def test_msp430_assembly_linking_and_disassembly_under_existing_isolation(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "test_msp430_probe.py").write_text('''import subprocess
from pathlib import Path

def test_installed_binary_hashes_match():
    subprocess.run(['sha256sum', '--check', '/opt/pwntools-msp430/binary-sha256.txt'], check=True, capture_output=True)

def test_msp430_assembler_and_linker():
    Path('/tmp/msp430.s').write_text('.text\\n.global _start\\n_start: mov #42, r0\\n')
    subprocess.run(['msp430-elf-as', '/tmp/msp430.s', '-o', '/tmp/msp430.o'], check=True, capture_output=True)
    # The upstream MSP430 default linker script places flash at 0x8000.
    subprocess.run(['msp430-elf-ld', '-e', '_start', '-Ttext=0x8000', '/tmp/msp430.o', '-o', '/tmp/msp430.elf'], check=True, capture_output=True)
    subprocess.run(['msp430-elf-objcopy', '-O', 'binary', '-j', '.text', '/tmp/msp430.elf', '/tmp/msp430.bin'], check=True, capture_output=True)
    assert Path('/tmp/msp430.bin').read_bytes() == bytes.fromhex('30402a00')
    output = subprocess.run(['msp430-elf-objdump', '-d', '/tmp/msp430.elf'], check=True, capture_output=True).stdout
    # mov immediate to r0 is rendered as the equivalent branch pseudoinstruction.
    assert b'br\\t#0x002a' in output

def test_pwntools_public_msp430_example():
    from pwn import asm
    assert asm('mov #42, r0', arch='msp430') == bytes.fromhex('30402a00')
''', encoding="utf-8")
    artifacts = Path(os.environ.get("AGENTLESS_PWNTOOLS_MSP430_ARTIFACTS", str(tmp_path / "logs")))
    runner = DockerTestRunner(os.environ["AGENTLESS_PWNTOOLS_MSP430_IMAGE"], artifacts,
                              memory_mb=8192, cpus=2, tmpfs_mb=4096,
                              pids_limit=2048, run_as_image_user=True)
    execution = runner.run(source, PublicTestCommand(
        ("sh", "-c", "cd /tmp/work && PWNLIB_NOTERM=1 python -m pytest -p no:cacheprovider --junitxml=/tmp/report.xml"),
        timeout_seconds=90, report=TestReport(ReportFormat.JUNIT_XML, "/tmp/report.xml"),
    ))
    assert execution.result.status.value == "pass", f"{execution.message}; {execution.artifact_directory}"
    assert len(execution.result.test_cases) == 3
