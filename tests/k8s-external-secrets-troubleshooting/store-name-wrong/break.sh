#!/usr/bin/env bash
# The ExternalSecret my-app-config points at a SecretStore named my-store; the store is
# called my-app-store. The sync fails and the target Secret is never created.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

kubectl apply -f - <<'YAML'
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: my-app-config
  namespace: my-namespace
spec:
  refreshInterval: 1m
  secretStoreRef:
    kind: SecretStore
    name: my-store
  target:
    name: my-app-config
  data:
    - secretKey: settings
      remoteRef:
        key: /my-app/settings
        version: v1
YAML
wait_for --for=condition=Ready=false externalsecret/my-app-config -n my-namespace
