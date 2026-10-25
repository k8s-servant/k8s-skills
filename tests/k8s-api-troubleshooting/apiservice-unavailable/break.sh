#!/usr/bin/env bash
# Register the aggregated API v1beta1.my-api.example.com, whose Service was removed, then
# delete my-namespace. The namespace controller cannot list the group, so the namespace
# stays Terminating.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

kubectl apply -f - <<'YAML'
apiVersion: apiregistration.k8s.io/v1
kind: APIService
metadata:
  name: v1beta1.my-api.example.com
spec:
  group: my-api.example.com
  version: v1beta1
  groupPriorityMinimum: 1000
  versionPriority: 15
  # The test has no backend at all, so there is no CA to give.
  insecureSkipTLSVerify: true
  service:
    name: my-api
    namespace: my-api-system
    port: 443
YAML
kubectl delete namespace my-namespace --wait=false
for _ in $(seq 1 36); do
  conditions="$(kubectl get namespace my-namespace \
    -o jsonpath='{range .status.conditions[*]}{.type}={.status}{"\n"}{end}' 2>/dev/null || true)"
  if [[ "$conditions" == *NamespaceDeletionDiscoveryFailure=True* ]]; then
    exit 0
  fi
  sleep 5
done
echo "my-namespace never reported the discovery failure" >&2
exit 1
