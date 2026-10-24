#!/usr/bin/env bash
# A ConstraintTemplate has a Rego syntax error (a missing closing brace), so Gatekeeper
# cannot compile it and never creates the K8sRequiredLabels constraint kind. Applying a
# constraint then fails with "no matches for kind". The script checks that it fails.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
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
YAML
for _ in $(seq 1 30); do
  if [[ -n "$(kubectl get constrainttemplate k8srequiredlabels -o jsonpath='{.status.byPod[*].errors}')" ]]; then
    break
  fi
  sleep 2
done
if kubectl apply -f - <<'YAML'
apiVersion: constraints.gatekeeper.sh/v1beta1
kind: K8sRequiredLabels
metadata:
  name: deployments-must-have-owner
spec:
  match:
    kinds:
      - apiGroups: ["apps"]
        kinds: ["Deployment"]
  parameters:
    labels: ["example.com/owner"]
YAML
then
  echo "the constraint was accepted; the template is not broken" >&2
  exit 1
fi
