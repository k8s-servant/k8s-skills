#!/usr/bin/env bash
# Remove the webhook configuration first, so nothing else is blocked, then the namespaces.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

kubectl delete validatingwebhookconfiguration my-webhook --ignore-not-found
kubectl delete namespace my-namespace my-webhook-system --ignore-not-found --wait=true --timeout=300s
