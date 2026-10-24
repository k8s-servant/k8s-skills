#!/usr/bin/env bash
# Create the namespace the scenario uses. Run this case on a fresh cluster: objects
# other cases left broken would be real findings.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

kubectl apply -f - <<'YAML'
apiVersion: v1
kind: Namespace
metadata:
  name: my-namespace
YAML
