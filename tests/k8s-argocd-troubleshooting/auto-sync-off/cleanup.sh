#!/usr/bin/env bash
# Remove the scenario's Applications and AppProject, and the namespace. Argo CD stays.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

kubectl delete applications.argoproj.io -n argocd -l example.com/scenario=argocd --ignore-not-found --wait=true
kubectl delete appprojects.argoproj.io -n argocd -l example.com/scenario=argocd --ignore-not-found
kubectl delete namespace my-namespace --ignore-not-found --wait=true
