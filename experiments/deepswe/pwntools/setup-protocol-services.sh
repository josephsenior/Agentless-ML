# Explicit shared HTTP/TLS diagnostic, not a public network or Google mirror.
. /opt/pwntools-setup-local-ssh-offline.sh
task_service_root=/tmp/pwntools-services
mkdir -p "$task_service_root"
chmod 700 "$task_service_root"
openssl req -x509 -newkey rsa:2048 -nodes -days 1 \
    -subj '/CN=Agentless offline protocol diagnostic' \
    -addext 'subjectAltName=DNS:pypi.org,DNS:httpbingo.org,DNS:google.com' \
    -addext 'basicConstraints=critical,CA:TRUE' \
    -keyout "$task_service_root/key.pem" -out "$task_service_root/cert.pem" \
    > "$task_service_root/certificate.log" 2>&1 || exit 125
chmod 600 "$task_service_root/key.pem"
/opt/pwntools-services/shared-services \
    -cert "$task_service_root/cert.pem" -key "$task_service_root/key.pem" \
    > "$task_service_root/requests.jsonl" 2>&1 &
task_service_pid=$!
trap 'kill "$task_service_pid" "$task_sshd_pid" 2>/dev/null || true; cat "$task_service_root/requests.jsonl" >&2' EXIT HUP INT TERM
export REQUESTS_CA_BUNDLE="$task_service_root/cert.pem"
task_service_ready=0
for task_attempt in 1 2 3 4 5; do
    if python /opt/pwntools-services/offline-services.py --check --protocol --cert "$REQUESTS_CA_BUNDLE" \
        > "$task_service_root/preflight.log" 2>&1; then
        task_service_ready=1
        break
    fi
    sleep 0.2
done
cat "$task_service_root/preflight.log" >&2
if [ "$task_service_ready" -ne 1 ]; then exit 125; fi
printf '%s\n' 'OFFLINE PROTOCOL-SERVICE DIAGNOSTIC: modified environment; shared TLS, real HTTP parser, closed failure-test ports' >&2
