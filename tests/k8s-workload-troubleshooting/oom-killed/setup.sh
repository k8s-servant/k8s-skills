#!/usr/bin/env bash
# Create the empty namespace the scenario uses.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

kubectl create namespace my-namespace
