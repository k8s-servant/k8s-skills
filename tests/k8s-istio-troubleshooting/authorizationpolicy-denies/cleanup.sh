#!/usr/bin/env bash
# Remove the scenario's namespaces. Istio stays installed.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

kubectl delete namespace my-namespace my-other-namespace --ignore-not-found --wait=true
