#!/usr/bin/env bash
# Remove the namespace and the ClusterIssuer. cert-manager stays installed.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

kubectl delete namespace my-namespace --ignore-not-found --wait=true
kubectl delete clusterissuer my-cluster-issuer --ignore-not-found
