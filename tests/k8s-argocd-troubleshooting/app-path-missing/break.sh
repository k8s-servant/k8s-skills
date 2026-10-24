#!/usr/bin/env bash
# The Application my-app points at a folder that does not exist in the repository
# (guestbook-ui instead of guestbook), so Argo CD cannot generate its manifests.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

kubectl apply -f - <<'YAML'
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: my-app
  namespace: argocd
  labels:
    example.com/scenario: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/argoproj/argocd-example-apps
    targetRevision: master
    path: guestbook-ui
  destination:
    server: https://kubernetes.default.svc
    namespace: my-namespace
  syncPolicy:
    automated: {}
YAML
for _ in $(seq 1 36); do
  if kubectl get application my-app -n argocd -o jsonpath='{.status.conditions[*].type}' | grep -q ComparisonError; then
    exit 0
  fi
  sleep 5
done
echo "my-app never reported a ComparisonError" >&2
exit 1
