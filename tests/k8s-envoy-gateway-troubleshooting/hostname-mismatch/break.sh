#!/usr/bin/env bash
# The HTTPRoute is for app.example.com, but the Gateway listener only takes
# my-app.example.com, so the route is not attached and requests get 404.
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
    - app.example.com
  rules:
    - backendRefs:
        - name: my-app
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
