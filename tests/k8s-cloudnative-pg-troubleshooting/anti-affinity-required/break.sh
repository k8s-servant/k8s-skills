#!/usr/bin/env bash
# The Cluster my-db wants 2 instances with pod anti-affinity "required", on a cluster with
# one schedulable node. The primary runs; the replica's join pod stays Pending and the
# Cluster stays at 1 of 2 ready instances.
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
  instances: 2
  imageName: ${CNPG_POSTGRES_IMAGE}
  storage:
    size: 1Gi
  affinity:
    enablePodAntiAffinity: true
    podAntiAffinityType: required
YAML
  then
    break
  fi
  sleep 5
done
wait_for --timeout=300s --for=jsonpath='{.status.phase}'="Creating a new replica" clusters.postgresql.cnpg.io/my-db -n my-namespace
for _ in $(seq 1 60); do
  if kubectl get pods -n my-namespace -l cnpg.io/jobRole=join \
    -o jsonpath='{.items[*].status.conditions[?(@.type=="PodScheduled")].reason}' | grep -q Unschedulable; then
    exit 0
  fi
  sleep 5
done
echo "the join pod was not reported Unschedulable" >&2
exit 1
