#!/usr/bin/env bash
# Taint the worker node for a maintenance that is over, then run my-app pinned to that
# node without a toleration, so its pods stay Pending.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
# shellcheck source=../../versions.env disable=SC1091
source "$(dirname "$0")/../../versions.env"
require_test_cluster

kubectl taint nodes k8s-skills-test-worker example.com/maintenance=true:NoSchedule --overwrite
kubectl apply -f - <<YAML
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
  namespace: my-namespace
spec:
  replicas: 2
  selector:
    matchLabels:
      app: my-app
  template:
    metadata:
      labels:
        app: my-app
    spec:
      nodeSelector:
        kubernetes.io/hostname: k8s-skills-test-worker
      containers:
        - name: app
          image: ${NGINX_IMAGE}
          resources:
            requests:
              cpu: 10m
              memory: 16Mi
            limits:
              memory: 64Mi
YAML
for _ in $(seq 1 24); do
  if kubectl get events -n my-namespace --field-selector reason=FailedScheduling \
    -o name | grep -q .; then
    exit 0
  fi
  sleep 5
done
echo "my-app pods were not reported unschedulable" >&2
exit 1
