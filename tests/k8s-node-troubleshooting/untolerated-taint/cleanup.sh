#!/usr/bin/env bash
# Remove the maintenance taint and the namespace.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

kubectl taint nodes k8s-skills-test-worker example.com/maintenance- 2>/dev/null || true
kubectl delete namespace my-namespace --ignore-not-found --wait=true
