#!/usr/bin/env bash
# Create my-namespace and the ServiceAccount my-app runs as.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

kubectl apply -f - <<'YAML'
apiVersion: v1
kind: Namespace
metadata:
  name: my-namespace
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: my-app
  namespace: my-namespace
YAML
