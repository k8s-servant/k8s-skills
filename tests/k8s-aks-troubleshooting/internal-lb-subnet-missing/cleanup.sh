#!/usr/bin/env bash
# Delete my-namespace and everything the scenario created in it.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

kubectl delete namespace my-namespace --ignore-not-found --timeout=300s
