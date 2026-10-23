#!/usr/bin/env bash
# Create or delete the throwaway kind cluster used by the scenario tests.
#
# Usage: tests/cluster.sh up [--cni calico] | down
# Only the cluster named k8s-skills-test is ever created or deleted here.
set -euo pipefail
# shellcheck source-path=SCRIPTDIR

# shellcheck source=lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
# shellcheck source=versions.env disable=SC1091
source "$(dirname "${BASH_SOURCE[0]}")/versions.env"

usage() {
  echo "usage: tests/cluster.sh up [--cni calico] | down" >&2
  exit 64
}

up() {
  local cni="" config=""
  if [[ "${1:-}" == "--cni" ]]; then
    cni="${2:-}"
    [[ "$cni" == "calico" ]] || usage
  elif [[ $# -gt 0 ]]; then
    usage
  fi

  mkdir -p "$REPO_ROOT/.kube"
  local args=(create cluster --name "$CLUSTER_NAME" --image "$KIND_NODE_IMAGE" --kubeconfig "$KUBECONFIG")

  if [[ "$cni" == "calico" ]]; then
    # NetworkPolicy scenarios need a CNI that enforces policies; kind's default does not.
    config="$(mktemp)"
    cat > "$config" <<'YAML'
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
networking:
  disableDefaultCNI: true
YAML
    args+=(--config "$config")
  fi

  kind "${args[@]}"
  [[ -z "$config" ]] || rm -f "$config"

  if [[ "$cni" == "calico" ]]; then
    kubectl apply -f "https://raw.githubusercontent.com/projectcalico/calico/${CALICO_VERSION}/manifests/calico.yaml"
  fi
  kubectl wait --for=condition=Ready nodes --all --timeout=300s
}

down() {
  kind delete cluster --name "$CLUSTER_NAME"
  rm -f "$REPO_ROOT/.kube/$CLUSTER_NAME" "$REPO_ROOT/.kube/agent"
}

case "${1:-}" in
  up) shift; up "$@" ;;
  down) down ;;
  *) usage ;;
esac
