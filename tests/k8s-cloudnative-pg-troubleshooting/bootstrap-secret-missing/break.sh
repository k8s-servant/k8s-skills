#!/usr/bin/env bash
# The Cluster my-db bootstraps its database with the owner's password from the Secret
# my-db-credentials, which nobody created. The initdb pod waits in
# CreateContainerConfigError and the Cluster stays in "Setting up primary".
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

# shellcheck source=../../versions.env disable=SC1091
source "$REPO_ROOT/tests/versions.env"
# The operator's webhook needs a moment after its Deployment is Available.
for _ in $(seq 1 30); do
  if kubectl apply -f - <<YAML
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: my-db
  namespace: my-namespace
spec:
  instances: 1
  imageName: ${CNPG_POSTGRES_IMAGE}
  storage:
    size: 1Gi
  bootstrap:
    initdb:
      database: app
      owner: app
      secret:
        name: my-db-credentials
YAML
  then
    break
  fi
  sleep 5
done
for _ in $(seq 1 60); do
  if kubectl get pods -n my-namespace -l cnpg.io/jobRole=initdb \
    -o jsonpath='{.items[*].status.containerStatuses[*].state.waiting.reason}' | grep -q CreateContainerConfigError; then
    exit 0
  fi
  sleep 5
done
echo "the initdb pod did not reach CreateContainerConfigError" >&2
exit 1
