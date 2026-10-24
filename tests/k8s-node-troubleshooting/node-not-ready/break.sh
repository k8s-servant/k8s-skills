#!/usr/bin/env bash
# Run my-app on the worker node, then stop that node's kubelet so the node stops
# reporting, and wait until its Ready condition is no longer True.
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
kubectl -n my-namespace rollout status deployment/my-app --timeout=120s

# kind nodes are containers; stopping the kubelet is how a node dies in real life.
docker exec k8s-skills-test-worker systemctl stop kubelet
for _ in $(seq 1 40); do
  ready="$(kubectl get node k8s-skills-test-worker \
    -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}')"
  if [[ "$ready" != "True" ]]; then
    exit 0
  fi
  sleep 5
done
echo "k8s-skills-test-worker is still Ready" >&2
exit 1
