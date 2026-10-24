#!/usr/bin/env bash
# Start the worker's kubelet again, wait for the node, and remove the namespace.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

docker exec k8s-skills-test-worker systemctl start kubelet
kubectl wait --for=condition=Ready node/k8s-skills-test-worker --timeout=180s
kubectl delete namespace my-namespace --ignore-not-found --wait=true
