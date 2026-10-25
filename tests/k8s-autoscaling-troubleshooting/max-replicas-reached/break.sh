#!/usr/bin/env bash
# Run my-app busy on CPU, with an HPA at 50% utilization and maxReplicas 3. It wants far
# more pods than 3, so it stops at the maximum.
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
          image: ${BUSYBOX_IMAGE}
          # Stands in for an app under steady load: it uses all the CPU it may.
          command: ["sh", "-c", "while true; do :; done"]
          resources:
            requests:
              cpu: 10m
              memory: 16Mi
            limits:
              cpu: 50m
              memory: 32Mi
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
  maxReplicas: 3
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 50
YAML
kubectl -n my-namespace rollout status deployment/my-app --timeout=120s
for _ in $(seq 1 48); do
  limited="$(kubectl get hpa my-app -n my-namespace -o jsonpath='{.status.conditions[?(@.type=="ScalingLimited")].reason}')"
  ready="$(kubectl get deployment my-app -n my-namespace -o jsonpath='{.status.readyReplicas}')"
  if [[ "$limited" == TooManyReplicas && "$ready" == 3 ]]; then
    exit 0
  fi
  sleep 5
done
echo "the HPA never reached its maximum" >&2
exit 1
