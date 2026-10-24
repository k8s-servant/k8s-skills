#!/usr/bin/env bash
# The ServiceMonitor for my-app names the endpoint port "metrics", but the Service
# port is named "http". Prometheus loads the ServiceMonitor and finds no target.
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
    release: my-prometheus
spec:
  selector:
    matchLabels:
      app: my-app
  endpoints:
    - port: metrics
      path: /metrics
      interval: 15s
YAML
sleep 45
