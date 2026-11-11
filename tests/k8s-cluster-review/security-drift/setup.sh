#!/usr/bin/env bash
# The clean decoy app, and my-namespace with no Pod Security labels. Run it on a fresh
# cluster: the prompt asks for a review of the whole cluster.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
# shellcheck source=../../versions.env disable=SC1091
source "$(dirname "$0")/../../versions.env"
# shellcheck source=../review.sh disable=SC1091
source "$(dirname "$0")/../review.sh"
require_test_cluster

review_decoy
kubectl create namespace my-namespace
