#!/usr/bin/env bash
# Install the Prometheus Operator (pinned in versions.env) and run a Prometheus in
# monitoring that picks up ServiceMonitors labelled release=my-prometheus in every
# namespace, and my-app (podinfo, metrics on the Service port named http) in
# my-namespace.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
# shellcheck source=../../versions.env disable=SC1091
source "$(dirname "$0")/../../versions.env"
require_test_cluster

"$REPO_ROOT/tests/addon.sh" prometheus-operator
kubectl apply -f - <<YAML
apiVersion: v1
kind: Namespace
metadata:
  name: monitoring
---
apiVersion: v1
kind: Namespace
metadata:
  name: my-namespace
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: prometheus
  namespace: monitoring
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: my-prometheus
rules:
  - apiGroups: [""]
    resources: [services, endpoints, pods]
    verbs: [get, list, watch]
  - apiGroups: [discovery.k8s.io]
    resources: [endpointslices]
    verbs: [get, list, watch]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: my-prometheus
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: my-prometheus
subjects:
  - kind: ServiceAccount
    name: prometheus
    namespace: monitoring
---
apiVersion: monitoring.coreos.com/v1
kind: Prometheus
metadata:
  name: my-prometheus
  namespace: monitoring
spec:
  image: ${PROMETHEUS_IMAGE}
  replicas: 1
  serviceAccountName: prometheus
  scrapeInterval: 15s
  serviceMonitorSelector:
    matchLabels:
      release: my-prometheus
  serviceMonitorNamespaceSelector: {}
  resources:
    requests:
      memory: 200Mi
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
  namespace: my-namespace
spec:
  replicas: 1
  selector:
    matchLabels:
      app: my-app
  template:
    metadata:
      labels:
        app: my-app
    spec:
      containers:
        - name: app
          image: ${PODINFO_IMAGE}
          ports:
            - name: http
              containerPort: 9898
          resources:
            requests:
              cpu: 10m
              memory: 32Mi
---
apiVersion: v1
kind: Service
metadata:
  name: my-app
  namespace: my-namespace
  labels:
    app: my-app
spec:
  selector:
    app: my-app
  ports:
    - name: http
      port: 9898
      targetPort: http
YAML
kubectl rollout status deployment/my-app -n my-namespace --timeout=180s
for _ in $(seq 1 60); do
  kubectl get statefulset prometheus-my-prometheus -n monitoring >/dev/null 2>&1 && break
  sleep 2
done
kubectl rollout status statefulset/prometheus-my-prometheus -n monitoring --timeout=300s
