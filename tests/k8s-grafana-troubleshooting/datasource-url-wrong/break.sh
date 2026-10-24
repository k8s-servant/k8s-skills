#!/usr/bin/env bash
# The Prometheus datasource's URL is changed to prometheus.monitoring.svc, a Service that
# does not exist (it is prometheus-operated). Grafana starts, but every query fails.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

kubectl apply -f - <<'YAML'
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
        url: http://prometheus.monitoring.svc:9090
        isDefault: true
YAML
kubectl rollout restart deployment/my-grafana -n monitoring
kubectl rollout status deployment/my-grafana -n monitoring --timeout=300s
