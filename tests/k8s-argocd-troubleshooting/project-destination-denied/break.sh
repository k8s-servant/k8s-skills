#!/usr/bin/env bash
# The AppProject my-project allows only the namespace my-other-namespace, but the
# Application my-app deploys into my-namespace, so Argo CD refuses the Application.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

kubectl apply -f - <<'YAML'
apiVersion: argoproj.io/v1alpha1
kind: AppProject
metadata:
  name: my-project
  namespace: argocd
  labels:
    example.com/scenario: argocd
spec:
  sourceRepos:
    - https://github.com/argoproj/argocd-example-apps
  destinations:
    - server: https://kubernetes.default.svc
      namespace: my-other-namespace
---
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: my-app
  namespace: argocd
  labels:
    example.com/scenario: argocd
spec:
  project: my-project
  source:
    repoURL: https://github.com/argoproj/argocd-example-apps
    targetRevision: master
    path: guestbook
  destination:
    server: https://kubernetes.default.svc
    namespace: my-namespace
  syncPolicy:
    automated: {}
YAML
for _ in $(seq 1 36); do
  if kubectl get application my-app -n argocd -o jsonpath='{.status.conditions[*].type}' | grep -q InvalidSpecError; then
    exit 0
  fi
  sleep 5
done
echo "my-app never reported an InvalidSpecError" >&2
exit 1
