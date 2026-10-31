#!/usr/bin/env bash
# The team in my-other-namespace publishes /api with its own HTTPRoute on the shared
# Gateway, but the listener only admits routes from my-namespace.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

kubectl apply -f - <<'YAML'
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: my-api
  namespace: my-other-namespace
spec:
  parentRefs:
    - name: my-gateway
      namespace: my-namespace
  hostnames:
    - my-app.example.com
  rules:
    - matches:
        - path:
            type: PathPrefix
            value: /api
      backendRefs:
        - name: my-api
          port: 80
YAML
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
