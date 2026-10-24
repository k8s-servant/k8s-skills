#!/usr/bin/env bash
# Run Grafana (my-grafana, pinned in versions.env) in monitoring, provisioned from
# ConfigMaps with a Prometheus datasource and the dashboard my-app. A podinfo pod behind
# the Service prometheus-operated stands in for Prometheus.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
# shellcheck source=../../versions.env disable=SC1091
source "$(dirname "$0")/../../versions.env"
require_test_cluster

kubectl apply -f - <<YAML
apiVersion: v1
kind: Namespace
metadata:
  name: monitoring
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: prometheus-stand-in
  namespace: monitoring
spec:
  replicas: 1
  selector:
    matchLabels:
      app: prometheus-stand-in
  template:
    metadata:
      labels:
        app: prometheus-stand-in
    spec:
      containers:
        - name: app
          image: ${PODINFO_IMAGE}
          ports:
            - name: http
              containerPort: 9898
---
apiVersion: v1
kind: Service
metadata:
  name: prometheus-operated
  namespace: monitoring
spec:
  selector:
    app: prometheus-stand-in
  ports:
    - name: web
      port: 9090
      targetPort: http
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: my-grafana-datasources
  namespace: monitoring
data:
  datasources.yaml: |
    apiVersion: 1
    datasources:
      - name: Prometheus
        type: prometheus
        uid: prometheus
        url: http://prometheus-operated.monitoring.svc:9090
        isDefault: true
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: my-grafana-dashboard-providers
  namespace: monitoring
data:
  dashboards.yaml: |
    apiVersion: 1
    providers:
      - name: default
        folder: Apps
        type: file
        options:
          path: /var/lib/grafana/dashboards
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: my-grafana-dashboards
  namespace: monitoring
data:
  my-app.json: |
    {"uid": "my-app", "title": "my-app", "schemaVersion": 41,
     "panels": [{"type": "timeseries", "title": "Requests",
                 "datasource": {"type": "prometheus", "uid": "prometheus"}}]}
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-grafana
  namespace: monitoring
spec:
  replicas: 1
  selector:
    matchLabels:
      app: my-grafana
  template:
    metadata:
      labels:
        app: my-grafana
    spec:
      securityContext:
        fsGroup: 472
      containers:
        - name: grafana
          image: ${GRAFANA_IMAGE}
          ports:
            - name: http
              containerPort: 3000
          readinessProbe:
            httpGet:
              path: /api/health
              port: http
          volumeMounts:
            - name: datasources
              mountPath: /etc/grafana/provisioning/datasources
            - name: dashboard-providers
              mountPath: /etc/grafana/provisioning/dashboards
            - name: dashboards
              mountPath: /var/lib/grafana/dashboards
      volumes:
        - name: datasources
          configMap:
            name: my-grafana-datasources
        - name: dashboard-providers
          configMap:
            name: my-grafana-dashboard-providers
        - name: dashboards
          configMap:
            name: my-grafana-dashboards
---
apiVersion: v1
kind: Service
metadata:
  name: my-grafana
  namespace: monitoring
spec:
  selector:
    app: my-grafana
  ports:
    - name: http
      port: 80
      targetPort: http
YAML
kubectl rollout status deployment/prometheus-stand-in -n monitoring --timeout=180s
kubectl rollout status deployment/my-grafana -n monitoring --timeout=300s
