#!/usr/bin/env bash
# Fill the worker node's allocatable CPU with the requests of an idle batch Deployment in
# another namespace, then run my-app pinned to the same node. The node does nothing, but
# its CPU is fully requested, so my-app's pods stay Pending with "Insufficient cpu".
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
# shellcheck source=../../versions.env disable=SC1091
source "$(dirname "$0")/../../versions.env"
require_test_cluster

cpu="$(kubectl get node k8s-skills-test-worker -o jsonpath='{.status.allocatable.cpu}')"
if [[ "$cpu" == *m ]]; then
  millis="${cpu%m}"
else
  millis=$((cpu * 1000))
fi
# Leave room for the node's own DaemonSet pods, but not for my-app's 500m.
filler=$((millis - 300))

kubectl apply -f - <<YAML
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-batch
  namespace: my-other-namespace
spec:
  replicas: 1
  selector:
    matchLabels:
      app: my-batch
  template:
    metadata:
      labels:
        app: my-batch
    spec:
      nodeSelector:
        kubernetes.io/hostname: k8s-skills-test-worker
      containers:
        - name: batch
          image: ${BUSYBOX_IMAGE}
          command: ["sleep", "3600"]
          resources:
            requests:
              cpu: ${filler}m
              memory: 16Mi
            limits:
              memory: 32Mi
YAML
kubectl -n my-other-namespace rollout status deployment/my-batch --timeout=120s

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
              cpu: 500m
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
