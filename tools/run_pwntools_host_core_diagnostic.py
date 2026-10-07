"""Opt-in, temporary WSL host change with saved recovery data and restoration.

Requires explicit approval for the host-wide change. Never run this as part
of an ordinary benchmark invocation or test collection.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMAGE = "agentless-ml/pwntools-offline:2026-10-08"
IMAGE_ID = "sha256:4d9295759148dbdb3b1a18fe58b25d7d4d4ae17d7f6223c3c09db138eeafc5ba"
EXPECTED_ORIGINAL = "|/wsl-capture-crash %t %E %p %s"
TEMPORARY = "core.%p"
WSL = ["wsl", "-d", "docker-desktop", "-u", "root", "--exec", "/sbin/sysctl"]
PROBE = r'''import hashlib, inspect, json, os
from pathlib import Path
from pwn import ELF, context, process
import pwnlib.elf.corefile as module
context.log_level='error'
source=Path(inspect.getsourcefile(module.CorefileFinder))
assert hashlib.sha256(source.read_bytes()).hexdigest() == 'd9f38a3c7c2dfcb13798304ca8ca29626ed9090ae1658ba4409d5149a2073492'
assert Path('/proc/sys/kernel/core_pattern').read_text().strip() == 'core.%p'
os.chdir('/tmp')
with context.local(arch='i386'):
    binary=ELF.from_assembly('mov eax, 3; xor ebx, ebx; mov ecx, esp; mov edx, 1; int 0x80; mov eax, 0xdeadbeef; jmp eax')
    child=process(binary.path)
    limits=[line for line in Path('/proc/%d/limits' % child.pid).read_text().splitlines() if 'core file size' in line]
    child.send(b'x')
    child.wait()
    assert child.poll() == -11
    core=child.corefile
    assert core.eip == core.eax == core.fault_addr == 0xdeadbeef
    assert core.signal == 11
    print(json.dumps({'automatic_core_retrieval':True,'core_path':core.path,'core_limit':limits,
        'eip':core.eip,'eax':core.eax,'fault_addr':core.fault_addr,'signal':core.signal,'uid':os.getuid()}))
'''


def read_setting(name: str) -> str:
    return subprocess.check_output([*WSL, "-n", name], timeout=30).decode("utf-8").strip()


def set_pattern(value: str) -> None:
    # --exec passes the pipe/spaces as a literal argument, never shell syntax.
    subprocess.run([*WSL, "-w", "kernel.core_pattern=" + value], check=True, timeout=30)


def restore(original: str) -> None:
    actual = read_setting("kernel.core_pattern")
    if actual not in (original, TEMPORARY):
        raise RuntimeError("Host setting changed concurrently; refusing to overwrite it. See saved recovery data.")
    if actual != original:
        set_pattern(original)
    if read_setting("kernel.core_pattern") != original:
        raise RuntimeError("Original host setting was not restored")


def write_evidence(directory: Path, evidence: dict) -> None:
    (directory / "host-setting.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply-temporary-host-setting", action="store_true",
                        help="Explicitly opt in after user approval; affects the WSL host, not just the test container")
    parser.add_argument("--artifacts", type=Path, default=ROOT.parent / "output/deepswe-survey/pwntools-host-core-2026-10-08")
    args = parser.parse_args()
    if not args.apply_temporary_host_setting:
        parser.error("Host change requires --apply-temporary-host-setting and explicit user approval")
    actual_image = subprocess.check_output(["docker", "image", "inspect", IMAGE, "--format", "{{.Id}}"], text=True).strip()
    if actual_image != IMAGE_ID:
        raise RuntimeError("Diagnostic image no longer matches its recorded pin")
    running = subprocess.check_output(["docker", "ps", "-q"], text=True).strip()
    if running:
        raise RuntimeError("Other containers are running; use a quiet testing window")
    original = read_setting("kernel.core_pattern")
    original_uses_pid = read_setting("kernel.core_uses_pid")
    if original != EXPECTED_ORIGINAL or original_uses_pid != "0":
        raise RuntimeError("Host settings differ from the approved assessment; aborting without changes")
    args.artifacts.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="diagnostic-", dir=args.artifacts))
    evidence = {"original_core_pattern": original, "temporary_core_pattern": TEMPORARY,
        "original_core_uses_pid": original_uses_pid, "image": IMAGE, "image_id": IMAGE_ID,
        "restored": False, "diagnostic_only": True, "canonical_readiness_changed": False}
    write_evidence(directory, evidence)
    quoted_original = original.replace("'", "''")
    (directory / "RECOVERY.txt").write_text(
        "If the controlling process is interrupted, inspect the current setting first.\n"
        "Do not overwrite an unrelated concurrent change. Restore with this PowerShell command:\n"
        "wsl -d docker-desktop -u root --exec /sbin/sysctl -w 'kernel.core_pattern=" + quoted_original + "'\n"
        "Verify: wsl -d docker-desktop -u root --exec /sbin/sysctl -n kernel.core_pattern\n",
        encoding="utf-8")
    print(f"Saved original setting and recovery instructions: {directory}", flush=True)
    try:
        set_pattern(TEMPORARY)
        if read_setting("kernel.core_pattern") != TEMPORARY:
            raise RuntimeError("Temporary host setting did not take effect")
        print("Temporary host setting verified. Running the isolated native crash probe.", flush=True)
        probe = subprocess.run(["docker", "run", "--rm", "-i", "--init", "--network=none", "--read-only",
            "--cap-drop=ALL", "--security-opt=no-new-privileges", "--memory=8192m", "--cpus=2",
            "--pids-limit=2048", "--tmpfs", "/tmp:rw,exec,nosuid,nodev,size=4096m,mode=1777",
            "--env", "PWNLIB_NOTERM=1", "--env", "PYTHONDONTWRITEBYTECODE=1",
            "--env", "XDG_CACHE_HOME=/tmp/pwntools-core-probe-cache", "--entrypoint", "python", IMAGE, "-"],
            input=PROBE.encode(), capture_output=True, timeout=90)
        (directory / "probe.stdout.log").write_bytes(probe.stdout)
        (directory / "probe.stderr.log").write_bytes(probe.stderr)
        evidence["probe_exit_code"] = probe.returncode
        print(probe.stdout.decode(errors="replace"), flush=True)
        print(probe.stderr.decode(errors="replace"), flush=True)
        if probe.returncode:
            raise RuntimeError("Native crash probe failed; will not run the broader schedule")
        print("Native core retrieval passed. Running the unchanged public Docker schedule.", flush=True)
        schedule = subprocess.run([sys.executable, str(ROOT / "tools/run_pwntools_native_tests.py"),
            "--image", IMAGE, "--public-docker-schedule", "--timeout-seconds", "1800",
            "--artifacts", str(directory / "public-schedule")], capture_output=True, timeout=2100, cwd=ROOT)
        (directory / "schedule.stdout.log").write_bytes(schedule.stdout)
        (directory / "schedule.stderr.log").write_bytes(schedule.stderr)
        evidence["schedule_exit_code"] = schedule.returncode
        evidence["pattern_after_schedule"] = read_setting("kernel.core_pattern")
        print(schedule.stdout.decode(errors="replace"), flush=True)
        print(schedule.stderr.decode(errors="replace"), flush=True)
        return schedule.returncode
    finally:
        try:
            restore(original)
            evidence["restored"] = True
            evidence["restored_core_pattern"] = read_setting("kernel.core_pattern")
            evidence["final_core_uses_pid"] = read_setting("kernel.core_uses_pid")
            if evidence["final_core_uses_pid"] != original_uses_pid:
                raise RuntimeError("core_uses_pid changed concurrently")
            print("Original WSL host setting restored and verified.", flush=True)
        finally:
            write_evidence(directory, evidence)


if __name__ == "__main__":
    raise SystemExit(main())
