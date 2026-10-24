#!/usr/bin/env bash
# A ClusterPolicy in Enforce mode requires the label example.com/team on every Pod.
# Kyverno also applies the rule to Deployments (autogen), so applying my-app, whose
# pod template has no such label, is denied. The script checks that the apply fails.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
# shellcheck source=../../versions.env disable=SC1091
source "$(dirname "$0")/../../versions.env"
require_test_cluster

kubectl apply -f - <<'YAML'
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: require-team-label
  labels:
    example.com/scenario: kyverno
spec:
  background: true
  rules:
    - name: check-team-label
      match:
        any:
          - resources:
              kinds:
                - Pod
      validate:
        failureAction: Enforce
        message: "Pods must have the label example.com/team."
        pattern:
          metadata:
            labels:
              example.com/team: "?*"
YAML
wait_for --for=condition=Ready clusterpolicy/require-team-label
if kubectl apply -f - <<YAML
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
then
  echo "the Deployment was accepted; the policy does not block it" >&2
  exit 1
fi
