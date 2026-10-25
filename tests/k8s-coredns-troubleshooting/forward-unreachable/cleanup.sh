#!/usr/bin/env bash
# Put the saved Corefile back, restart CoreDNS, and remove the namespace.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
# shellcheck source=../coredns.sh disable=SC1091
source "$(dirname "$0")/../coredns.sh"
require_test_cluster

coredns_restore
kubectl delete namespace my-namespace --ignore-not-found --wait=true
