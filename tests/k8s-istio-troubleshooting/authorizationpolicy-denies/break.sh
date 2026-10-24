#!/usr/bin/env bash
# An AuthorizationPolicy on my-app allows only the frontend service account, so the
# requests of my-web (service account my-web) are denied with 403.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

kubectl apply -f - <<'YAML'
apiVersion: security.istio.io/v1
kind: AuthorizationPolicy
metadata:
  name: my-app-allow
  namespace: my-namespace
spec:
  selector:
    matchLabels:
      app: my-app
  action: ALLOW
  rules:
    - from:
        - source:
            principals: ["cluster.local/ns/my-namespace/sa/frontend"]
YAML
for _ in $(seq 1 24); do
  if kubectl logs -n my-namespace deployment/my-web -c web --since=20s | grep -q failed; then
    exit 0
  fi
  sleep 5
done
echo "my-web never failed to reach my-app" >&2
exit 1
