#!/usr/bin/env bash
# Install a pinned third-party add-on into the kind test cluster, for the ecosystem
# skills' scenarios. The manifest is checked against a pinned checksum before it is
# applied. Running it again re-applies the same version, so scenarios can call it in
# their setup.sh.
#
# Usage: tests/addon.sh <name>
# Names: cert-manager, flux, argocd, kyverno, gatekeeper, external-secrets,
# prometheus-operator, istio (Helm charts, so it needs helm), envoy-gateway, keda,
# metrics-server
set -euo pipefail
# shellcheck source-path=SCRIPTDIR

# shellcheck source=lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
# shellcheck source=versions.env disable=SC1091
source "$(dirname "${BASH_SOURCE[0]}")/versions.env"

usage() {
  echo "usage: tests/addon.sh cert-manager|flux|argocd|kyverno|gatekeeper|external-secrets|prometheus-operator|istio|envoy-gateway|keda|metrics-server" >&2
  exit 64
}

[[ $# -eq 1 ]] || usage
own_namespaces=false
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
  external-secrets)
    url="https://github.com/external-secrets/external-secrets/releases/download/${ESO_VERSION}/external-secrets.yaml"
    sum="$ESO_MANIFEST_SHA256"
    # The release manifest is rendered with every object in the default namespace.
    namespace="default"
    ;;
  prometheus-operator)
    url="https://github.com/prometheus-operator/prometheus-operator/releases/download/${PROMETHEUS_OPERATOR_VERSION}/bundle.yaml"
    sum="$PROMETHEUS_OPERATOR_MANIFEST_SHA256"
    # The bundle installs the operator in the default namespace.
    namespace="default"
    ;;
  envoy-gateway)
    url="https://github.com/envoyproxy/gateway/releases/download/${ENVOY_GATEWAY_VERSION}/install.yaml"
    sum="$ENVOY_GATEWAY_MANIFEST_SHA256"
    namespace="envoy-gateway-system"
    ;;
  keda)
    url="https://github.com/kedacore/keda/releases/download/${KEDA_VERSION}/keda-${KEDA_VERSION#v}.yaml"
    sum="$KEDA_MANIFEST_SHA256"
    namespace="keda"
    # The manifest names its own namespaces, one object in kube-system.
    own_namespaces=true
    ;;
  metrics-server)
    url="https://github.com/kubernetes-sigs/metrics-server/releases/download/${METRICS_SERVER_VERSION}/components.yaml"
    sum="$METRICS_SERVER_MANIFEST_SHA256"
    namespace="kube-system"
    ;;
  istio) ;;
  *) usage ;;
esac

require_test_cluster

manifest=""
base_chart=""
trap 'rm -f "$manifest" "$base_chart"' EXIT

if [[ "$1" == "istio" ]]; then
  # Istio ships Helm charts only: base (CRDs) first, then istiod. The demo profile keeps
  # requests small and writes Envoy access logs to stdout, which the scenarios read.
  charts="https://blob.istio.io/istio-release/charts"
  base_chart="$(mktemp)"
  manifest="$(mktemp)"
  fetch_verified "$charts/base-${ISTIO_VERSION}.tgz" "$ISTIO_BASE_CHART_SHA256" "$base_chart"
  fetch_verified "$charts/istiod-${ISTIO_VERSION}.tgz" "$ISTIOD_CHART_SHA256" "$manifest"
  helm upgrade --install istio-base "$base_chart" -n istio-system --create-namespace \
    --set defaultRevision=default >&2
  helm upgrade --install istiod "$manifest" -n istio-system --set profile=demo --wait >&2
  exit 0
fi

manifest="$(mktemp)"
fetch_verified "$url" "$sum" "$manifest"
# Some manifests (Argo CD) leave their objects' namespace to `kubectl apply -n`.
if ! kubectl get namespace "$namespace" >/dev/null 2>&1; then
  kubectl create namespace "$namespace" >&2
fi
# Server-side apply: some CRDs are larger than the client-side annotation limit.
if [[ "$own_namespaces" == true ]]; then
  kubectl apply --server-side --force-conflicts -f "$manifest" >&2
else
  kubectl apply --server-side --force-conflicts -n "$namespace" -f "$manifest" >&2
fi
if [[ "$1" == "metrics-server" ]]; then
  # kind's kubelet serving certificates carry no IP SANs, so metrics-server cannot verify
  # them and never becomes Ready ("For testing purposes only", its README says).
  kubectl patch deployment metrics-server -n kube-system --type=json \
    -p '[{"op": "add", "path": "/spec/template/spec/containers/0/args/-", "value": "--kubelet-insecure-tls"}]' >&2
fi
kubectl wait --for=condition=Available deployment --all -n "$namespace" --timeout=300s >&2
for statefulset in $(kubectl get statefulsets -n "$namespace" -o name); do
  kubectl rollout status "$statefulset" -n "$namespace" --timeout=300s >&2
done
