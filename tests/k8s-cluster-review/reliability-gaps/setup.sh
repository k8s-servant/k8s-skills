#!/usr/bin/env bash
# The clean decoy app, and my-namespace with the same Pod Security label and
# NetworkPolicies, so the security group has nothing to find there.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
# shellcheck source=../../versions.env disable=SC1091
source "$(dirname "$0")/../../versions.env"
# shellcheck source=../review.sh disable=SC1091
source "$(dirname "$0")/../review.sh"
require_test_cluster

review_decoy
review_clean_namespace my-namespace
