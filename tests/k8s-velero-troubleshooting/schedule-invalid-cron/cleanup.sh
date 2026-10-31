#!/usr/bin/env bash
# Remove the scenario's Velero objects and namespace. Restarting the object store empties
# its bucket (an emptyDir), so the backups do not sync back.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

kubectl delete restores.velero.io,schedules.velero.io --all -n velero --ignore-not-found
kubectl delete backupstoragelocations.velero.io my-backups -n velero --ignore-not-found
kubectl rollout restart deployment/object-store -n velero
kubectl rollout status deployment/object-store -n velero --timeout=180s
kubectl delete backups.velero.io --all -n velero --ignore-not-found
kubectl delete namespace my-namespace --ignore-not-found --wait=true
