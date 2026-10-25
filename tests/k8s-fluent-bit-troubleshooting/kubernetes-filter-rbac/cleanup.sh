#!/usr/bin/env bash
# Remove the namespace and Fluent Bit's cluster-scoped RBAC.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

kubectl delete clusterrolebinding my-fluent-bit --ignore-not-found
kubectl delete clusterrole my-fluent-bit --ignore-not-found
kubectl delete namespace my-namespace --ignore-not-found --wait=true
