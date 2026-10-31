#!/usr/bin/env bash
# A PodDisruptionBudget asks for one my-app pod to stay available, and my-app has only one,
# so no pod may ever be evicted: draining the node for the upgrade would wait forever.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

kubectl apply -f - <<'YAML'
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
for _ in $(seq 1 24); do
  if [[ "$(kubectl get pdb my-app -n my-namespace -o jsonpath='{.status.currentHealthy}')" == 1 ]]; then
    exit 0
  fi
  sleep 5
done
echo "the PDB never saw my-app's pod" >&2
exit 1
