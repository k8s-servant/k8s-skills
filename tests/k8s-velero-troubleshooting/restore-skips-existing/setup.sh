#!/usr/bin/env bash
# Install Velero (pinned in versions.env) with its test object store, a namespace with
# one ConfigMap, and a completed backup of it.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

"$REPO_ROOT/tests/addon.sh" velero
kubectl apply -f - <<'YAML'
apiVersion: v1
kind: Namespace
metadata:
  name: my-namespace
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: my-app-config
  namespace: my-namespace
data:
  mode: "safe"
YAML
kubectl apply -f - <<'YAML'
apiVersion: velero.io/v1
kind: Backup
metadata:
  name: my-app-backup
  namespace: velero
spec:
  includedNamespaces: [my-namespace]
YAML
wait_for --for=jsonpath='{.status.phase}'=Completed backups.velero.io/my-app-backup -n velero
