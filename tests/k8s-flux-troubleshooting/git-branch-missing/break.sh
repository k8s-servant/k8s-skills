#!/usr/bin/env bash
# The GitRepository for my-app follows a branch that does not exist, so Flux never gets
# an artifact and the Kustomization that deploys my-app never applies anything.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

kubectl apply -f - <<'YAML'
apiVersion: source.toolkit.fluxcd.io/v1
kind: GitRepository
metadata:
  name: my-app
  namespace: flux-system
  labels:
    example.com/scenario: flux
spec:
  interval: 1m
  url: https://github.com/stefanprodan/podinfo
  ref:
    branch: release-6.15
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: my-app
  namespace: flux-system
  labels:
    example.com/scenario: flux
spec:
  interval: 5m
  path: ./kustomize
  prune: true
  sourceRef:
    kind: GitRepository
    name: my-app
  targetNamespace: my-namespace
YAML
wait_for --for=condition=Ready=false gitrepository/my-app -n flux-system
wait_for --for=condition=Ready=false kustomization/my-app -n flux-system
