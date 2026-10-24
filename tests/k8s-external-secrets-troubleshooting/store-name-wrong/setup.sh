#!/usr/bin/env bash
# Install External Secrets (pinned in versions.env) and create the namespace and a fake
# SecretStore. The fake provider keeps its dummy values in the store's spec, not in a
# Secret.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

"$REPO_ROOT/tests/addon.sh" external-secrets
kubectl apply -f - <<'YAML'
apiVersion: v1
kind: Namespace
metadata:
  name: my-namespace
YAML
# The webhook needs a moment after its Deployment is Available.
for _ in $(seq 1 30); do
  if kubectl apply -f - <<'YAML'
apiVersion: external-secrets.io/v1
kind: SecretStore
metadata:
  name: my-app-store
  namespace: my-namespace
spec:
  provider:
    fake:
      data:
        - key: /my-app/settings
          value: "log-level=info"
          version: v1
        - key: /my-app/feature-flags
          value: "new-ui=false"
          version: v1
YAML
  then
    break
  fi
  sleep 5
done
wait_for --for=condition=Ready secretstore/my-app-store -n my-namespace
