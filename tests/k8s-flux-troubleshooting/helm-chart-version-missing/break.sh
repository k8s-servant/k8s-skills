#!/usr/bin/env bash
# The HelmRelease for my-app asks for a podinfo chart version the Helm repository does
# not have, so Flux cannot build the HelmChart and never installs the release.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

kubectl apply -f - <<'YAML'
apiVersion: source.toolkit.fluxcd.io/v1
kind: HelmRepository
metadata:
  name: podinfo
  namespace: flux-system
  labels:
    example.com/scenario: flux
spec:
  interval: 10m
  url: https://stefanprodan.github.io/podinfo
---
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
  name: my-app
  namespace: flux-system
  labels:
    example.com/scenario: flux
spec:
  interval: 5m
  releaseName: my-app
  targetNamespace: my-namespace
  chart:
    spec:
      chart: podinfo
      version: "6.51.0"
      sourceRef:
        kind: HelmRepository
        name: podinfo
YAML
wait_for --for=condition=Ready helmrepository/podinfo -n flux-system
wait_for --for=condition=Ready=false helmrelease/my-app -n flux-system
