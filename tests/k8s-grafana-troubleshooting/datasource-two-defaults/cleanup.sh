#!/usr/bin/env bash
# Remove Grafana, the stand-in and the namespace.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

kubectl delete namespace monitoring --ignore-not-found --wait=true
