#!/usr/bin/env bash
# The dashboard file for my-app gets a trailing comma, which is not valid JSON. Grafana
# skips the file, logs the error and keeps running without the dashboard.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

kubectl apply -f - <<'YAML'
apiVersion: v1
kind: ConfigMap
metadata:
  name: my-grafana-dashboards
  namespace: monitoring
data:
  my-app.json: |
    {"uid": "my-app", "title": "my-app", "schemaVersion": 41,
     "panels": [{"type": "timeseries", "title": "Requests",
                 "datasource": {"type": "prometheus", "uid": "prometheus"}},]}
YAML
kubectl rollout restart deployment/my-grafana -n monitoring
kubectl rollout status deployment/my-grafana -n monitoring --timeout=300s
sleep 10
