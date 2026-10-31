#!/usr/bin/env bash
# A second BackupStorageLocation, my-backups, names the bucket my-app-backups, which the
# object store does not have (it has velero). The location turns Unavailable and the
# backup my-app-offsite to it fails validation.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

kubectl apply -f - <<'YAML'
apiVersion: velero.io/v1
kind: BackupStorageLocation
metadata:
  name: my-backups
  namespace: velero
spec:
  provider: aws
  objectStorage:
    bucket: my-app-backups
  config:
    region: us-east-1
    s3ForcePathStyle: "true"
    s3Url: http://object-store.velero.svc:7070
YAML
wait_for --for=jsonpath='{.status.phase}'=Unavailable backupstoragelocations.velero.io/my-backups -n velero
kubectl apply -f - <<'YAML'
apiVersion: velero.io/v1
kind: Backup
metadata:
  name: my-app-offsite
  namespace: velero
spec:
  includedNamespaces: [my-namespace]
  storageLocation: my-backups
YAML
wait_for --for=jsonpath='{.status.phase}'=FailedValidation backups.velero.io/my-app-offsite -n velero
