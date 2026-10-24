#!/usr/bin/env bash
# The ServiceMonitor for my-app has no release=my-prometheus label, which the
# Prometheus' serviceMonitorSelector requires, so Prometheus never scrapes my-app.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

kubectl apply -f - <<'YAML'
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: my-app
  namespace: my-namespace
  labels:
    app: my-app
spec:
  selector:
    matchLabels:
      app: my-app
  endpoints:
    - port: http
      path: /metrics
      interval: 15s
YAML
sleep 45
