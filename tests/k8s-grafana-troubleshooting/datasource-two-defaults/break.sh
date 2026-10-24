#!/usr/bin/env bash
# Someone adds a second Prometheus datasource, also marked isDefault. Grafana refuses
# the provisioning file at start and exits, so the pod crash-loops.
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
        url: http://prometheus-operated.monitoring.svc:9090
        isDefault: true
      - name: Prometheus long-term
        type: prometheus
        uid: prometheus-long-term
        url: http://prometheus-operated.monitoring.svc:9090
        isDefault: true
YAML
kubectl rollout restart deployment/my-grafana -n monitoring
for _ in $(seq 1 36); do
  if kubectl get pods -n monitoring -l app=my-grafana -o jsonpath='{.items[*].status.containerStatuses[*].restartCount}' | grep -q '[1-9]'; then
    exit 0
  fi
  sleep 5
done
echo "my-grafana never restarted" >&2
exit 1
