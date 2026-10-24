#!/usr/bin/env bash
# A CiliumNetworkPolicy on my-app allows my-web in, but its HTTP rule allows only GET
# /healthz. my-web requests /, which Cilium's proxy answers with 403 Access denied.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

kubectl apply -f - <<'YAML'
apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: my-app-http
  namespace: my-namespace
spec:
  endpointSelector:
    matchLabels:
      app: my-app
  ingress:
    - fromEndpoints:
        - matchLabels:
            app: my-web
      toPorts:
        - ports:
            - port: "80"
              protocol: TCP
          rules:
            http:
              - method: GET
                path: /healthz
YAML
for _ in $(seq 1 24); do
  if kubectl logs -n my-namespace deployment/my-web --since=20s | grep -q failed; then
    exit 0
  fi
  sleep 5
done
echo "my-web never failed to reach my-app" >&2
exit 1
