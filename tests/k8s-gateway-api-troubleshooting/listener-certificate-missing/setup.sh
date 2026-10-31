#!/usr/bin/env bash
# Install Envoy Gateway (pinned in versions.env) with a GatewayClass eg, and run my-app
# (nginx) in my-namespace and my-api in my-other-namespace, each behind a Service.
# A Gateway my-gateway has an http listener for my-app.example.com and an HTTPRoute
# my-app; my-web calls https through it.
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
kubectl apply -f - <<YAML
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: my-gateway
  namespace: my-namespace
spec:
  gatewayClassName: eg
  infrastructure:
    parametersRef:
      group: gateway.envoyproxy.io
      kind: EnvoyProxy
      name: my-proxy
  listeners:
    - name: http
      protocol: HTTP
      port: 80
      hostname: my-app.example.com
YAML
wait_for --for=condition=Programmed gateway/my-gateway -n my-namespace
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
        - name: my-app
          port: 80
YAML
envoy="$(kubectl get service -n envoy-gateway-system \
  -l gateway.envoyproxy.io/owning-gateway-name=my-gateway -o jsonpath='{.items[0].metadata.name}')"
kubectl apply -f - <<YAML
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-web
  namespace: my-namespace
spec:
  replicas: 1
  selector:
    matchLabels:
      app: my-web
  template:
    metadata:
      labels:
        app: my-web
    spec:
      containers:
        - name: web
          image: ${BUSYBOX_IMAGE}
          # Calls the Gateway for https://my-app.example.com/ every 5 seconds and logs each result.
          command:
            - sh
            - -c
            - |
              while true; do
                if out=\$(wget -qO /dev/null -T 3 --header "Host: my-app.example.com" https://${envoy}.envoy-gateway-system/ 2>&1); then
                  echo "\$(date) GET https://my-app.example.com/ ok"
                else
                  echo "\$(date) GET https://my-app.example.com/ failed: \$out"
                fi
                sleep 5
              done
YAML
kubectl rollout status deployment/my-web -n my-namespace --timeout=180s
