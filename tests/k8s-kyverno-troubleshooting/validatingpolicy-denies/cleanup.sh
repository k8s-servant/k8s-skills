#!/usr/bin/env bash
# Remove the scenario's policies and the namespace. Kyverno stays installed.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

kubectl delete clusterpolicies.kyverno.io,validatingpolicies.policies.kyverno.io -l example.com/scenario=kyverno --ignore-not-found
kubectl delete namespace my-namespace --ignore-not-found --wait=true
