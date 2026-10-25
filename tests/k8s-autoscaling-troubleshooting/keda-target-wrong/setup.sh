#!/usr/bin/env bash
# Install metrics-server and KEDA, and create my-namespace.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

"$REPO_ROOT/tests/addon.sh" metrics-server
"$REPO_ROOT/tests/addon.sh" keda
kubectl create namespace my-namespace --dry-run=client -o yaml | kubectl apply -f -
