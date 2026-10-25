#!/usr/bin/env bash
# An internal LoadBalancer Service whose subnet annotation names a subnet that does not
# exist in the cluster's virtual network. No Azure resource is created.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

kubectl apply -f - <<'YAML'
apiVersion: v1
kind: Service
metadata:
  name: my-app
  namespace: my-namespace
  annotations:
    service.beta.kubernetes.io/azure-load-balancer-internal: "true"
    service.beta.kubernetes.io/azure-load-balancer-internal-subnet: my-missing-subnet
spec:
  type: LoadBalancer
  selector:
    app: my-app
  ports:
    - port: 80
      targetPort: 8080
YAML

# Wait for the cloud provider to report the failure.
for _ in $(seq 1 36); do
  if kubectl events -n my-namespace --for service/my-app 2>/dev/null | grep -q SyncLoadBalancerFailed; then
    exit 0
  fi
  sleep 5
done
echo "no SyncLoadBalancerFailed event for my-app after 3 minutes" >&2
exit 1
