#!/usr/bin/env bash
# A new GatewayClass my-class names the controller gateway.envoyproxy.io/gateway-controller,
# which no controller claims (Envoy Gateway's is gatewayclass-controller). The Gateway
# my-gateway uses it, so nothing ever picks the Gateway up.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

kubectl apply -f - <<'YAML'
apiVersion: gateway.networking.k8s.io/v1
kind: GatewayClass
metadata:
  name: my-class
spec:
  controllerName: gateway.envoyproxy.io/gateway-controller
---
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: my-gateway
  namespace: my-namespace
spec:
  gatewayClassName: my-class
  listeners:
    - name: http
      protocol: HTTP
      port: 80
      hostname: my-app.example.com
---
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
        - name: my-app
          port: 80
YAML
# Envoy Gateway would answer within seconds; make sure it stays unclaimed.
sleep 20
reason="$(kubectl get gatewayclass my-class -o jsonpath='{.status.conditions[?(@.type=="Accepted")].reason}')"
if [[ "$reason" != Pending ]]; then
  echo "GatewayClass my-class is not Pending: $reason" >&2
  exit 1
fi
