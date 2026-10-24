#!/usr/bin/env bash
# Remove the scenario's constraints and template, bring the webhook back, and remove
# the namespace. Gatekeeper stays installed.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

kubectl scale deployment/gatekeeper-controller-manager -n gatekeeper-system --replicas=3
kubectl rollout status deployment/gatekeeper-controller-manager -n gatekeeper-system --timeout=180s
if kubectl get crd k8srequiredlabels.constraints.gatekeeper.sh >/dev/null 2>&1; then
  kubectl delete k8srequiredlabels --all --ignore-not-found
fi
kubectl delete constrainttemplates -l example.com/scenario=gatekeeper --ignore-not-found
kubectl delete namespace my-namespace --ignore-not-found --wait=true
