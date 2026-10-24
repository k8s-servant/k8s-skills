#!/usr/bin/env bash
# The ServiceMonitor for my-app scrapes /metric instead of /metrics. podinfo answers
# 404, so the target is down.
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
    - port: http
      path: /metric
      interval: 15s
YAML
sleep 45
