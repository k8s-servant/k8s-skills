#!/usr/bin/env bash
# The Application my-app has no automated sync policy, so Argo CD notices the
# difference between Git and the cluster (OutOfSync) but never deploys it.
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
    path: guestbook
  destination:
    server: https://kubernetes.default.svc
    namespace: my-namespace
YAML
for _ in $(seq 1 36); do
  if [[ "$(kubectl get application my-app -n argocd -o jsonpath='{.status.sync.status}')" == "OutOfSync" ]]; then
    exit 0
  fi
  sleep 5
done
echo "my-app never turned OutOfSync" >&2
exit 1
