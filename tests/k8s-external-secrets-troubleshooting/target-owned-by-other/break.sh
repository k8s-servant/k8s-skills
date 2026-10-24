#!/usr/bin/env bash
# Two ExternalSecrets write the same target Secret my-app-config. The first one owns it;
# the second, my-app-flags, cannot take it over and never syncs.
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
    name: my-app-store
  target:
    name: my-app-config
  data:
    - secretKey: settings
      remoteRef:
        key: /my-app/settings
        version: v1
YAML
wait_for --for=condition=Ready externalsecret/my-app-config -n my-namespace
kubectl apply -f - <<'YAML'
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: my-app-flags
  namespace: my-namespace
spec:
  refreshInterval: 1m
  secretStoreRef:
    kind: SecretStore
    name: my-app-store
  target:
    name: my-app-config
  data:
    - secretKey: feature-flags
      remoteRef:
        key: /my-app/feature-flags
        version: v1
YAML
wait_for --for=condition=Ready=false externalsecret/my-app-flags -n my-namespace
