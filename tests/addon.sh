#!/usr/bin/env bash
# Install a pinned third-party add-on into the kind test cluster, for the ecosystem
# skills' scenarios. The manifest is checked against a pinned checksum before it is
# applied. Running it again re-applies the same version, so scenarios can call it in
# their setup.sh.
#
# Usage: tests/addon.sh <name>
# Names: cert-manager, flux, argocd, kyverno, gatekeeper
set -euo pipefail
# shellcheck source-path=SCRIPTDIR

# shellcheck source=lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
# shellcheck source=versions.env disable=SC1091
source "$(dirname "${BASH_SOURCE[0]}")/versions.env"

usage() {
  echo "usage: tests/addon.sh cert-manager|flux|argocd|kyverno|gatekeeper" >&2
  exit 64
}

[[ $# -eq 1 ]] || usage
case "$1" in
  cert-manager)
    url="https://github.com/cert-manager/cert-manager/releases/download/${CERT_MANAGER_VERSION}/cert-manager.yaml"
    sum="$CERT_MANAGER_MANIFEST_SHA256"
    namespace="cert-manager"
    ;;
  flux)
    url="https://github.com/fluxcd/flux2/releases/download/${FLUX_VERSION}/install.yaml"
    sum="$FLUX_MANIFEST_SHA256"
    namespace="flux-system"
    ;;
  argocd)
    url="https://raw.githubusercontent.com/argoproj/argo-cd/${ARGOCD_VERSION}/manifests/install.yaml"
    sum="$ARGOCD_MANIFEST_SHA256"
    namespace="argocd"
    ;;
  kyverno)
    url="https://github.com/kyverno/kyverno/releases/download/${KYVERNO_VERSION}/install.yaml"
    sum="$KYVERNO_MANIFEST_SHA256"
    namespace="kyverno"
    ;;
  gatekeeper)
    url="https://raw.githubusercontent.com/open-policy-agent/gatekeeper/${GATEKEEPER_VERSION}/deploy/gatekeeper.yaml"
    sum="$GATEKEEPER_MANIFEST_SHA256"
    namespace="gatekeeper-system"
    ;;
  *) usage ;;
esac

require_test_cluster

manifest=""
trap 'rm -f "$manifest"' EXIT
manifest="$(mktemp)"
fetch_verified "$url" "$sum" "$manifest"
# Some manifests (Argo CD) leave their objects' namespace to `kubectl apply -n`.
if ! kubectl get namespace "$namespace" >/dev/null 2>&1; then
  kubectl create namespace "$namespace" >&2
fi
# Server-side apply: some CRDs are larger than the client-side annotation limit.
kubectl apply --server-side --force-conflicts -n "$namespace" -f "$manifest" >&2
kubectl wait --for=condition=Available deployment --all -n "$namespace" --timeout=300s >&2
for statefulset in $(kubectl get statefulsets -n "$namespace" -o name); do
  kubectl rollout status "$statefulset" -n "$namespace" --timeout=300s >&2
done
