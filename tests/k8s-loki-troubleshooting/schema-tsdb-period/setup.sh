#!/usr/bin/env bash
# Create my-namespace for Loki and its client.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

kubectl create namespace my-namespace --dry-run=client -o yaml | kubectl apply -f -
