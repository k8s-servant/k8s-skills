#!/usr/bin/env bash
# The GitRepository works, but the Kustomization points at a folder that does not exist
# in the repository (./kustomize/overlays/production; the manifests are in ./kustomize),
# so nothing is applied.
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
    tag: 6.15.0
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
  path: ./kustomize/overlays/production
  prune: true
  sourceRef:
    kind: GitRepository
    name: my-app
  targetNamespace: my-namespace
YAML
wait_for --for=condition=Ready gitrepository/my-app -n flux-system
wait_for --for=condition=Ready=false kustomization/my-app -n flux-system
