#!/usr/bin/env bash
# The same constraint is in place, but the Gatekeeper webhook is scaled to zero. Its
# validating webhook fails open (failurePolicy Ignore), so my-app, which lacks the
# required label, is admitted. Only the audit reports the violation.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
# shellcheck source=../../versions.env disable=SC1091
source "$(dirname "$0")/../../versions.env"
require_test_cluster

kubectl apply -f - <<'YAML'
apiVersion: templates.gatekeeper.sh/v1
kind: ConstraintTemplate
metadata:
  name: k8srequiredlabels
  labels:
    example.com/scenario: gatekeeper
spec:
  crd:
    spec:
      names:
        kind: K8sRequiredLabels
      validation:
        openAPIV3Schema:
          type: object
          properties:
            labels:
              type: array
              items:
                type: string
  targets:
    - target: admission.k8s.gatekeeper.sh
      rego: |
        package k8srequiredlabels

        violation[{"msg": msg}] {
          provided := {label | input.review.object.metadata.labels[label]}
          required := {label | label := input.parameters.labels[_]}
          missing := required - provided
          count(missing) > 0
          msg := sprintf("you must provide labels: %v", [missing])
        }
YAML
for _ in $(seq 1 30); do
  kubectl get crd k8srequiredlabels.constraints.gatekeeper.sh >/dev/null 2>&1 && break
  sleep 2
done
kubectl wait --for=condition=Established crd/k8srequiredlabels.constraints.gatekeeper.sh --timeout=60s
kubectl apply -f - <<'YAML'
apiVersion: constraints.gatekeeper.sh/v1beta1
kind: K8sRequiredLabels
metadata:
  name: deployments-must-have-owner
spec:
  enforcementAction: deny
  match:
    kinds:
      - apiGroups: ["apps"]
        kinds: ["Deployment"]
    namespaces: ["my-namespace"]
  parameters:
    labels: ["example.com/owner"]
YAML
# Wait until every webhook pod enforces the constraint.
for _ in $(seq 1 60); do
  if [[ "$(kubectl get k8srequiredlabels deployments-must-have-owner -o jsonpath='{.status.byPod[*].enforced}')" == *true* ]]; then
    break
  fi
  sleep 2
done
sleep 5
kubectl scale deployment/gatekeeper-controller-manager -n gatekeeper-system --replicas=0
kubectl wait --for=delete pod -n gatekeeper-system -l control-plane=controller-manager --timeout=120s
kubectl apply -f - <<YAML
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
  namespace: my-namespace
spec:
  replicas: 1
  selector:
    matchLabels:
      app: my-app
  template:
    metadata:
      labels:
        app: my-app
    spec:
      containers:
        - name: app
          image: ${NGINX_IMAGE}
YAML
for _ in $(seq 1 60); do
  if [[ "$(kubectl get k8srequiredlabels deployments-must-have-owner -o jsonpath='{.status.totalViolations}')" -ge 1 ]]; then
    exit 0
  fi
  sleep 5
done
echo "the audit never reported the violation" >&2
exit 1
