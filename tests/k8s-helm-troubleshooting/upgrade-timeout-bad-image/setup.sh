#!/usr/bin/env bash
# Create the namespace and install release my-app (podinfo, pinned in versions.env)
# with helm 4. The chart comes from ghcr.io, so the cluster needs internet access.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
# shellcheck source=../../versions.env disable=SC1091
source "$(dirname "$0")/../../versions.env"
require_test_cluster

if [[ "$(helm version --short 2>/dev/null)" != v4.* ]]; then
  echo "this scenario needs helm 4 on PATH" >&2
  exit 1
fi
kubectl apply -f - <<'YAML'
apiVersion: v1
kind: Namespace
metadata:
  name: my-namespace
YAML
helm install my-app oci://ghcr.io/stefanprodan/charts/podinfo --version "$PODINFO_CHART_VERSION" \
  -n my-namespace --wait --timeout 3m
