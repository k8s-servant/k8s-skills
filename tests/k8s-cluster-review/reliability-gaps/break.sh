#!/usr/bin/env bash
# my-app runs one replica with no readiness probe and no requests, and a PDB asks for
# that one pod to stay available, so it can never be evicted.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
# shellcheck source=../../versions.env disable=SC1091
source "$(dirname "$0")/../../versions.env"
# shellcheck source=../review.sh disable=SC1091
source "$(dirname "$0")/../review.sh"
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
      securityContext: ${RESTRICTED_POD}
      containers:
        - name: app
          image: ${PODINFO_IMAGE}
          ports:
            - containerPort: 9898
          securityContext: ${RESTRICTED_CONTAINER}
---
apiVersion: v1
kind: Service
metadata:
  name: my-app
  namespace: my-namespace
spec:
  selector:
    app: my-app
  ports:
    - port: 9898
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: my-app
  namespace: my-namespace
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app: my-app
YAML
kubectl rollout status deployment/my-app -n my-namespace --timeout=180s
for _ in $(seq 1 24); do
  if [[ "$(kubectl get pdb my-app -n my-namespace -o jsonpath='{.status.currentHealthy}')" == 1 ]]; then
    exit 0
  fi
  sleep 5
done
echo "the PDB never saw my-app's pod" >&2
exit 1
