#!/usr/bin/env bash
# Remove the APIService, so my-namespace can finish deleting, then the other namespace.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

kubectl delete apiservice v1beta1.my-api.example.com --ignore-not-found
kubectl delete namespace my-namespace my-api-system --ignore-not-found --wait=true --timeout=300s
