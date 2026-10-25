#!/usr/bin/env bash
# Create my-namespace with an app in it, and the namespace an aggregated API used to run in.
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
kind: ConfigMap
metadata:
  name: my-app
  namespace: my-namespace
data:
  greeting: hello
---
apiVersion: v1
kind: Namespace
metadata:
  name: my-api-system
YAML
