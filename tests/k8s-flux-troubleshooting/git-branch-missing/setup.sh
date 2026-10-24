#!/usr/bin/env bash
# Install Flux (pinned in versions.env) and create the namespace my-app deploys into.
# Flux pulls podinfo from GitHub, so the cluster needs internet access.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

"$REPO_ROOT/tests/addon.sh" flux
kubectl apply -f - <<'YAML'
apiVersion: v1
kind: Namespace
metadata:
  name: my-namespace
YAML
