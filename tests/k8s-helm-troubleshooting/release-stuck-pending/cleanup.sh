#!/usr/bin/env bash
# Remove the release and the namespace.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

helm uninstall my-app -n my-namespace --ignore-not-found --wait
kubectl delete namespace my-namespace --ignore-not-found --wait=true
