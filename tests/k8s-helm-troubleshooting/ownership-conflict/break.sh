#!/usr/bin/env bash
# Someone created the Service my-app-podinfo by hand. Installing release my-app, whose
# chart renders a Service of that name, fails: Helm will not take over an object that
# lacks its ownership label and annotations.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
# shellcheck source=../../versions.env disable=SC1091
source "$(dirname "$0")/../../versions.env"
require_test_cluster

kubectl create service clusterip my-app-podinfo --tcp=9898:9898 -n my-namespace
if helm install my-app oci://ghcr.io/stefanprodan/charts/podinfo --version "$PODINFO_CHART_VERSION" \
  -n my-namespace --wait --timeout 2m; then
  echo "the install worked; the scenario is not broken" >&2
  exit 1
fi
