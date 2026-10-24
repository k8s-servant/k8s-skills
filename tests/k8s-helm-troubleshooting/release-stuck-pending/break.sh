#!/usr/bin/env bash
# Start an upgrade of my-app that is slow to become ready, and kill helm while it waits,
# as when a CI job is cancelled. The release stays pending-upgrade, so every later
# upgrade fails with "another operation (install/upgrade/rollback) is in progress".
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
# shellcheck source=../../versions.env disable=SC1091
source "$(dirname "$0")/../../versions.env"
require_test_cluster

release_status() {
  # Read the whole output first: grep -q on a pipe would cut helm off (SIGPIPE).
  local out
  out="$(helm status my-app -n my-namespace 2>/dev/null || true)"
  [[ "$out" == *"STATUS: $1"* ]]
}

helm upgrade my-app oci://ghcr.io/stefanprodan/charts/podinfo --version "$PODINFO_CHART_VERSION" \
  -n my-namespace --set replicaCount=2 --set probes.readiness.initialDelaySeconds=90 \
  --wait --timeout 5m >/dev/null 2>&1 &
pid=$!
for _ in $(seq 1 60); do
  if release_status pending-upgrade; then
    break
  fi
  sleep 1
done
kill -9 "$pid"
wait "$pid" 2>/dev/null || true
if ! release_status pending-upgrade; then
  echo "the release is not pending-upgrade" >&2
  exit 1
fi
