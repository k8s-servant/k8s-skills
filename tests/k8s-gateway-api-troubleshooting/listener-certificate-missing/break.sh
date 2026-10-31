#!/usr/bin/env bash
# Add an https listener whose certificateRefs names the TLS Secret my-app-tls, which was
# never created. The listener has no certificate and is not programmed; http keeps
# working. The scenario never creates, reads or touches any Secret.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

kubectl patch gateway my-gateway -n my-namespace --type=json -p '[{"op": "add", "path": "/spec/listeners/-", "value": {"name": "https", "protocol": "HTTPS", "port": 443, "hostname": "my-app.example.com", "tls": {"mode": "Terminate", "certificateRefs": [{"name": "my-app-tls"}]}}}]'
# Give Envoy the new config, then wait until my-web logs a failure.
sleep 20
for _ in $(seq 1 24); do
  if kubectl logs -n my-namespace deployment/my-web --since=15s | grep -q failed; then
    exit 0
  fi
  sleep 5
done
echo "my-web never failed" >&2
exit 1
