#!/usr/bin/env bash
# Remove the namespace and the cluster-scoped objects the scenario made.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

kubectl delete clusterrole my-app-node-reader --ignore-not-found
kubectl delete namespace my-namespace --ignore-not-found --wait=true
