#!/usr/bin/env bash
# Bring the webhook back and remove the namespace. cert-manager stays installed.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

kubectl scale deployment/cert-manager-webhook -n cert-manager --replicas=1
kubectl rollout status deployment/cert-manager-webhook -n cert-manager --timeout=180s
kubectl delete namespace my-namespace --ignore-not-found --wait=true
