#!/usr/bin/env bash
# Upgrade my-app to an image tag that does not exist. The new pod cannot pull its
# image, helm --wait times out, and the release is marked failed. With one replica
# and maxUnavailable 1, the old pod is already gone, so my-app is down.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
# shellcheck source=../../versions.env disable=SC1091
source "$(dirname "$0")/../../versions.env"
require_test_cluster

if helm upgrade my-app oci://ghcr.io/stefanprodan/charts/podinfo --version "$PODINFO_CHART_VERSION" \
  -n my-namespace --set image.tag=6.51.0 --wait --timeout 60s; then
  echo "the upgrade worked; the scenario is not broken" >&2
  exit 1
fi
