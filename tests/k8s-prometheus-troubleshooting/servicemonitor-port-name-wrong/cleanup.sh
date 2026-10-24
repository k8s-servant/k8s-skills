#!/usr/bin/env bash
# Remove Prometheus, the app and their namespaces. The operator stays installed.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

kubectl delete namespace my-namespace monitoring --ignore-not-found --wait=true
kubectl delete clusterrolebinding,clusterrole my-prometheus --ignore-not-found
