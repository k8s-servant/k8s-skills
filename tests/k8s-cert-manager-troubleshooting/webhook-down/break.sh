#!/usr/bin/env bash
# The cert-manager webhook is scaled to zero, as after a bad upgrade or a node drain
# with no replica left. Every create or update of a cert-manager resource is then
# rejected by the API server. The script checks that applying a Certificate fails.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

kubectl scale deployment/cert-manager-webhook -n cert-manager --replicas=0
kubectl wait --for=delete pod -n cert-manager -l app.kubernetes.io/component=webhook --timeout=120s
if kubectl apply -f - <<'YAML'
apiVersion: cert-manager.io/v1
kind: Issuer
metadata:
  name: my-issuer
  namespace: my-namespace
spec:
  selfSigned: {}
YAML
then
  echo "applying an Issuer still worked; the webhook is not down" >&2
  exit 1
fi
