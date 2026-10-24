#!/usr/bin/env bash
# Check the cluster has a worker node (tests/cluster.sh up --workers 1), then create the
# namespaces the scenario uses.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

if ! kubectl get node k8s-skills-test-worker >/dev/null 2>&1; then
  echo "this scenario needs a worker node: tests/cluster.sh up --workers 1" >&2
  exit 1
fi
kubectl apply -f - <<'YAML'
apiVersion: v1
kind: Namespace
metadata:
  name: my-namespace
---
apiVersion: v1
kind: Namespace
metadata:
  name: my-other-namespace
YAML
