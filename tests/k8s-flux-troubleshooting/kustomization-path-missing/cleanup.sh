#!/usr/bin/env bash
# Remove the scenario's Flux objects and the namespace. Flux stays installed.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

kubectl delete kustomizations.kustomize.toolkit.fluxcd.io,helmreleases.helm.toolkit.fluxcd.io \
  -n flux-system -l example.com/scenario=flux --ignore-not-found --wait=true
kubectl delete gitrepositories.source.toolkit.fluxcd.io,helmrepositories.source.toolkit.fluxcd.io \
  -n flux-system -l example.com/scenario=flux --ignore-not-found
kubectl delete namespace my-namespace --ignore-not-found --wait=true
