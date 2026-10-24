#!/usr/bin/env bash
# Create the namespaces the scenario uses: my-app runs in my-namespace, its client
# my-web in my-other-namespace.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

if ! kubectl get daemonset calico-node -n kube-system >/dev/null 2>&1; then
  echo "this scenario needs NetworkPolicy enforcement: tests/cluster.sh up --cni calico" >&2
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
