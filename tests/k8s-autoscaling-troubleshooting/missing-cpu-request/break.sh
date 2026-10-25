#!/usr/bin/env bash
# Run my-app with an HPA that targets 50% CPU utilization. The container sets no CPU
# request, so utilization has no denominator and the HPA cannot compute a replica count.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
# shellcheck source=../../versions.env disable=SC1091
source "$(dirname "$0")/../../versions.env"
require_test_cluster

kubectl apply -f - <<YAML
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
          image: ${NGINX_IMAGE}
          ports:
            - containerPort: 80
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: my-app
  namespace: my-namespace
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: my-app
  minReplicas: 1
  maxReplicas: 5
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 50
YAML
kubectl -n my-namespace rollout status deployment/my-app --timeout=120s
for _ in $(seq 1 36); do
  status="$(kubectl get hpa my-app -n my-namespace -o jsonpath='{.status.conditions[?(@.type=="ScalingActive")].message}')"
  if [[ "$status" == *"missing request for cpu"* ]]; then
    exit 0
  fi
  sleep 5
done
echo "the HPA never reported the missing CPU request" >&2
exit 1
