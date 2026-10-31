#!/usr/bin/env bash
# Someone changes my-app-config after the backup, then restores my-namespace from
# my-app-backup. The ConfigMap exists, so Velero skips it with a warning and the restore
# is Completed: the bad value stays.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

kubectl patch configmap my-app-config -n my-namespace --type=merge -p '{"data":{"mode":"broken"}}'
kubectl apply -f - <<'YAML'
apiVersion: velero.io/v1
kind: Restore
metadata:
  name: my-app-restore
  namespace: velero
spec:
  backupName: my-app-backup
  includedNamespaces: [my-namespace]
YAML
wait_for --for=jsonpath='{.status.phase}'=Completed restores.velero.io/my-app-restore -n velero
