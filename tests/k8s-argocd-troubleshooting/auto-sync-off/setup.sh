#!/usr/bin/env bash
# Install Argo CD (pinned in versions.env) and create the namespace my-app deploys into.
# Argo CD reads argocd-example-apps from GitHub, so the cluster needs internet access.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

"$REPO_ROOT/tests/addon.sh" argocd
kubectl apply -f - <<'YAML'
apiVersion: v1
kind: Namespace
metadata:
  name: my-namespace
YAML
