#!/usr/bin/env bash
# A ClusterPolicy meant to forbid the :latest tag runs in Audit mode, so Kyverno only
# reports the violation and my-app with busybox:latest is admitted and runs.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

kubectl apply -f - <<'YAML'
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: disallow-latest-tag
  labels:
    example.com/scenario: kyverno
spec:
  background: true
  rules:
    - name: require-image-tag
      match:
        any:
          - resources:
              kinds:
                - Pod
      validate:
        failureAction: Audit
        message: "An image tag other than latest is required."
        pattern:
          spec:
            containers:
              - image: "!*:latest"
YAML
wait_for --for=condition=Ready clusterpolicy/disallow-latest-tag
kubectl apply -f - <<'YAML'
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
          image: busybox:latest
          command: ["sleep", "3600"]
YAML
kubectl rollout status deployment/my-app -n my-namespace --timeout=120s
for _ in $(seq 1 36); do
  if kubectl get policyreports -n my-namespace -o jsonpath='{.items[*].summary.fail}' | grep -q '[1-9]'; then
    exit 0
  fi
  sleep 5
done
echo "no failing policy report appeared" >&2
exit 1
