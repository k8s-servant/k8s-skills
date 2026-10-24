#!/usr/bin/env bash
# A CEL ValidatingPolicy forbids Services of type NodePort in my-namespace. Creating
# the Service my-app as a NodePort is denied. The script checks that the apply fails.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

kubectl apply -f - <<'YAML'
apiVersion: policies.kyverno.io/v1
kind: ValidatingPolicy
metadata:
  name: disallow-nodeport
  labels:
    example.com/scenario: kyverno
spec:
  validationActions:
    - Deny
  matchConstraints:
    resourceRules:
      - apiGroups: [""]
        apiVersions: ["v1"]
        operations: ["CREATE", "UPDATE"]
        resources: ["services"]
  validations:
    - expression: "object.spec.type != 'NodePort'"
      message: "Services of type NodePort are not allowed."
YAML
sleep 10
if kubectl apply -f - <<'YAML'
apiVersion: v1
kind: Service
metadata:
  name: my-app
  namespace: my-namespace
spec:
  type: NodePort
  selector:
    app: my-app
  ports:
    - port: 80
YAML
then
  echo "the Service was accepted; the policy does not deny it" >&2
  exit 1
fi
