#!/usr/bin/env bash
# The HTTPRoute in my-namespace sends to my-api in my-other-namespace, but no
# ReferenceGrant in my-other-namespace allows it. Envoy Gateway answers 500.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

kubectl apply -f - <<'YAML'
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: my-app
  namespace: my-namespace
spec:
  parentRefs:
    - name: my-gateway
  hostnames:
    - my-app.example.com
  rules:
    - backendRefs:
        - name: my-api
          namespace: my-other-namespace
          port: 80
YAML
# Without a route the Gateway already answers 404; give Envoy the new config first.
sleep 20
for _ in $(seq 1 24); do
  if kubectl logs -n my-namespace deployment/my-web --since=15s | grep -q failed; then
    exit 0
  fi
  sleep 5
done
echo "my-web never failed" >&2
exit 1
