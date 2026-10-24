#!/usr/bin/env bash
# A VirtualService sends all my-app traffic to the DestinationRule subset v2, but every
# my-app pod is version v1, so Envoy has no endpoint for the route and answers 503.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

kubectl apply -f - <<'YAML'
apiVersion: networking.istio.io/v1
kind: DestinationRule
metadata:
  name: my-app
  namespace: my-namespace
spec:
  host: my-app.my-namespace.svc.cluster.local
  subsets:
    - name: v1
      labels:
        version: v1
    - name: v2
      labels:
        version: v2
---
apiVersion: networking.istio.io/v1
kind: VirtualService
metadata:
  name: my-app
  namespace: my-namespace
spec:
  hosts:
    - my-app.my-namespace.svc.cluster.local
  http:
    - route:
        - destination:
            host: my-app.my-namespace.svc.cluster.local
            subset: v2
YAML
for _ in $(seq 1 24); do
  if kubectl logs -n my-namespace deployment/my-web -c web --since=20s | grep -q failed; then
    exit 0
  fi
  sleep 5
done
echo "my-web never failed to reach my-app" >&2
exit 1
