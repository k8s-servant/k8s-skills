#!/usr/bin/env bash
# A CiliumNetworkPolicy on my-web allows egress only to my-app on port 80. Egress to
# kube-dns is not allowed, so my-web cannot resolve my-app's name any more.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

kubectl apply -f - <<'YAML'
apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: my-web-egress
  namespace: my-namespace
spec:
  endpointSelector:
    matchLabels:
      app: my-web
  egress:
    - toEndpoints:
        - matchLabels:
            app: my-app
      toPorts:
        - ports:
            - port: "80"
              protocol: TCP
YAML
for _ in $(seq 1 24); do
  if kubectl logs -n my-namespace deployment/my-web --since=20s | grep -q failed; then
    exit 0
  fi
  sleep 5
done
echo "my-web never failed to reach my-app" >&2
exit 1
