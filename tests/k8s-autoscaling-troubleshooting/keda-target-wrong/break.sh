#!/usr/bin/env bash
# Run my-app and a KEDA ScaledObject that should scale it to 2 replicas on a cron
# schedule that is always active. Its scaleTargetRef names my-app-v2, which does not
# exist, so KEDA creates no HPA and my-app stays at 1 replica.
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
          resources:
            requests:
              cpu: 10m
              memory: 16Mi
            limits:
              memory: 64Mi
---
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: my-app
  namespace: my-namespace
spec:
  scaleTargetRef:
    name: my-app-v2
  minReplicaCount: 1
  maxReplicaCount: 4
  triggers:
    - type: cron
      metadata:
        timezone: Etc/UTC
        start: "0 * * * *"
        end: "59 * * * *"
        desiredReplicas: "2"
YAML
kubectl -n my-namespace rollout status deployment/my-app --timeout=120s
for _ in $(seq 1 24); do
  ready="$(kubectl get scaledobject my-app -n my-namespace -o jsonpath='{.status.conditions[?(@.type=="Ready")].reason}')"
  if [[ "$ready" == ScaledObjectCheckFailed ]]; then
    exit 0
  fi
  sleep 5
done
echo "KEDA never reported the missing target" >&2
exit 1
