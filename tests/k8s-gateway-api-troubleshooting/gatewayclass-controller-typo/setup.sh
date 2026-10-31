#!/usr/bin/env bash
# Install Envoy Gateway (pinned in versions.env) with a GatewayClass eg, and run my-app
# (nginx) in my-namespace and my-api in my-other-namespace, each behind a Service.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
# shellcheck source=../../versions.env disable=SC1091
source "$(dirname "$0")/../../versions.env"
require_test_cluster

"$REPO_ROOT/tests/addon.sh" envoy-gateway
kubectl apply -f - <<YAML
apiVersion: gateway.networking.k8s.io/v1
kind: GatewayClass
metadata:
  name: eg
spec:
  controllerName: gateway.envoyproxy.io/gatewayclass-controller
---
apiVersion: v1
kind: Namespace
metadata:
  name: my-namespace
---
apiVersion: v1
kind: Namespace
metadata:
  name: my-other-namespace
---
apiVersion: gateway.envoyproxy.io/v1alpha1
kind: EnvoyProxy
metadata:
  name: my-proxy
  namespace: my-namespace
spec:
  provider:
    type: Kubernetes
    kubernetes:
      envoyService:
        type: ClusterIP
YAML
for ns in my-namespace my-other-namespace; do
  name=my-app; [[ "$ns" == my-other-namespace ]] && name=my-api
  kubectl apply -f - <<YAML
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ${name}
  namespace: ${ns}
spec:
  replicas: 1
  selector:
    matchLabels:
      app: ${name}
  template:
    metadata:
      labels:
        app: ${name}
    spec:
      containers:
        - name: app
          image: ${NGINX_IMAGE}
          ports:
            - name: http
              containerPort: 80
---
apiVersion: v1
kind: Service
metadata:
  name: ${name}
  namespace: ${ns}
spec:
  selector:
    app: ${name}
  ports:
    - name: http
      port: 80
      targetPort: http
YAML
done
kubectl rollout status deployment/my-app -n my-namespace --timeout=180s
kubectl rollout status deployment/my-api -n my-other-namespace --timeout=180s
