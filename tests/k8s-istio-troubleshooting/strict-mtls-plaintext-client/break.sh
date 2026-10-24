#!/usr/bin/env bash
# my-namespace now requires mTLS (PeerAuthentication STRICT). my-web runs in
# my-other-namespace without a sidecar and speaks plain HTTP, so my-app's sidecar resets
# its connections.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

kubectl apply -f - <<'YAML'
apiVersion: security.istio.io/v1
kind: PeerAuthentication
metadata:
  name: default
  namespace: my-namespace
spec:
  mtls:
    mode: STRICT
YAML
for _ in $(seq 1 24); do
  if kubectl logs -n my-other-namespace deployment/my-web -c web --since=20s | grep -q failed; then
    exit 0
  fi
  sleep 5
done
echo "my-web never failed to reach my-app" >&2
exit 1
