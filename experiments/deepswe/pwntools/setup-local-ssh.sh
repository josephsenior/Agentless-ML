#!/bin/sh
# Source inside an isolated, disposable diagnostic container only.
# No host keys, passwords, published ports, privileged mode or host network.
set -eu
# Match the account's advertised home; aligned images link it into /tmp.
export HOME="$(getent passwd travis | cut -d: -f6)"
task_ssh_user_home="$HOME"
# /tmp is a fresh mount at runtime, so the image's home link starts dangling.
mkdir -p /tmp/pwntools-ssh-user
mkdir -p "$HOME/.ssh" "$task_ssh_user_home/.ssh" /tmp/pwntools-sshd
chmod 700 "$HOME" "$HOME/.ssh" "$task_ssh_user_home" "$task_ssh_user_home/.ssh"
ssh-keygen -q -t ed25519 -f "$HOME/.ssh/id_ed25519" -N ''
ssh-keygen -q -t ed25519 -f /tmp/pwntools-sshd/host_key -N ''
printf 'from="127.0.0.1",no-agent-forwarding,no-X11-forwarding %s\n' \
    "$(cat "$HOME/.ssh/id_ed25519.pub")" > "$task_ssh_user_home/.ssh/authorized_keys"
chmod 600 "$task_ssh_user_home/.ssh/authorized_keys"
cat > "$HOME/.ssh/config" <<PWNTOOLS_CLIENT_CONFIG
Host example.pwnme
    User travis
    HostName 127.0.0.1
    IdentityFile $HOME/.ssh/id_ed25519
    IdentitiesOnly yes
    StrictHostKeyChecking yes
    UserKnownHostsFile $HOME/.ssh/known_hosts
PWNTOOLS_CLIENT_CONFIG
printf 'example.pwnme,127.0.0.1 %s\n' "$(cat /tmp/pwntools-sshd/host_key.pub)" > "$HOME/.ssh/known_hosts"
cat > /tmp/pwntools-sshd/config <<'PWNTOOLS_SERVER_CONFIG'
Port 22
ListenAddress 127.0.0.1
HostKey /tmp/pwntools-sshd/host_key
PidFile /tmp/pwntools-sshd/sshd.pid
AuthorizedKeysFile .ssh/authorized_keys
AllowUsers travis
PermitRootLogin no
PubkeyAuthentication yes
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitEmptyPasswords no
UsePAM no
StrictModes yes
AllowAgentForwarding no
X11Forwarding no
AllowTcpForwarding yes
GatewayPorts no
PermitTunnel no
PrintLastLog no
# Public uploads expect 0664. Set the SFTP mask without changing local defaults.
Subsystem sftp internal-sftp -u 0002
PWNTOOLS_SERVER_CONFIG
/usr/sbin/sshd -t -f /tmp/pwntools-sshd/config
/usr/sbin/sshd -D -e -f /tmp/pwntools-sshd/config > /tmp/pwntools-sshd/log 2>&1 &
task_sshd_pid=$!
trap 'kill "$task_sshd_pid" 2>/dev/null || true' EXIT HUP INT TERM
# A failed startup must not become a test failure or an empty passing report.
task_ssh_ready=0
for task_attempt in 1 2 3 4 5; do
    if ssh -o BatchMode=yes -o ConnectTimeout=1 example.pwnme true; then
        task_ssh_ready=1
        break
    fi
    sleep 0.2
done
if [ "$task_ssh_ready" -ne 1 ]; then
    cat /tmp/pwntools-sshd/log >&2
    exit 125
fi
