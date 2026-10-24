#!/usr/bin/env bash
# Create the namespace. The scenarios run helm (version 4) against the test cluster,
# and pull the podinfo chart from ghcr.io.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
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
