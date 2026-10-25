#!/usr/bin/env bash
# Remove the namespace and the CRD.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

kubectl delete namespace my-namespace --ignore-not-found --wait=true --timeout=300s
kubectl delete crd widgets.my-api.example.com --ignore-not-found
