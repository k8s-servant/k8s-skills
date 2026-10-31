#!/usr/bin/env bash
# The Cluster my-db asks for the StorageClass fast-ssd, which does not exist on kind. Its
# first PVC stays Pending, so the initdb pod cannot be scheduled and the Cluster stays
# in "Setting up primary".
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
    storageClass: fast-ssd
YAML
  then
    break
  fi
  sleep 5
done
wait_for --for=jsonpath='{.status.phase}'="Setting up primary" clusters.postgresql.cnpg.io/my-db -n my-namespace
wait_for --for=jsonpath='{.status.phase}'=Pending pvc/my-db-1 -n my-namespace
