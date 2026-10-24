#!/usr/bin/env bash
# Remove everything the scenario created.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

kubectl delete namespace my-namespace --ignore-not-found --wait=true
