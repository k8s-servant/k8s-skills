#!/usr/bin/env bash
# The daily Schedule my-app-daily has the hour 25 in its cron expression, so it fails
# validation and never creates a backup.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

kubectl apply -f - <<'YAML'
apiVersion: velero.io/v1
kind: Schedule
metadata:
  name: my-app-daily
  namespace: velero
spec:
  schedule: "0 25 * * *"
  template:
    includedNamespaces: [my-namespace]
    ttl: 720h0m0s
YAML
wait_for --for=jsonpath='{.status.phase}'=FailedValidation schedules.velero.io/my-app-daily -n velero
