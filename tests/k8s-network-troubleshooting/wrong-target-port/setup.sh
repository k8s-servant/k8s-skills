#!/usr/bin/env bash
# Create the namespaces the scenario uses: my-app runs in my-namespace, its client
# my-web in my-other-namespace.
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
kind: Namespace
metadata:
  name: my-other-namespace
YAML
