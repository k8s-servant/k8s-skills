#!/usr/bin/env bash
# Create or delete the throwaway kind cluster used by the scenario tests.
#
# Usage: tests/cluster.sh up [--cni calico] [--workers N] | down
# Only the cluster named k8s-skills-test is ever created or deleted here.
set -euo pipefail
# shellcheck source-path=SCRIPTDIR

# shellcheck source=lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
# shellcheck source=versions.env disable=SC1091
source "$(dirname "${BASH_SOURCE[0]}")/versions.env"

usage() {
  echo "usage: tests/cluster.sh up [--cni calico] [--workers N] | down" >&2
  exit 64
}

up() {
  local cni="" workers=0 config="" manifest="" i
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --cni)
        cni="${2:-}"
        [[ "$cni" == "calico" ]] || usage
        shift 2
        ;;
      --workers)
        workers="${2:-}"
        [[ "$workers" =~ ^[1-9][0-9]*$ ]] || usage
        shift 2
        ;;
      *) usage ;;
    esac
  done

  if [[ "$cni" == "calico" ]]; then
    manifest="$(mktemp)"
    fetch_calico "$manifest"
  fi

  mkdir -p "$REPO_ROOT/.kube"
  local args=(create cluster --name "$CLUSTER_NAME" --image "$KIND_NODE_IMAGE" --kubeconfig "$KUBECONFIG")

  if [[ -n "$cni" || "$workers" -gt 0 ]]; then
    config="$(mktemp)"
    printf 'kind: Cluster\napiVersion: kind.x-k8s.io/v1alpha4\n' > "$config"
    if [[ "$cni" == "calico" ]]; then
      # NetworkPolicy scenarios need a CNI that enforces policies; kind's default does not.
      printf 'networking:\n  disableDefaultCNI: true\n' >> "$config"
    fi
    if [[ "$workers" -gt 0 ]]; then
      # Node scenarios break a worker; the control plane must keep running.
      printf 'nodes:\n  - role: control-plane\n' >> "$config"
      for ((i = 0; i < workers; i++)); do
        printf '  - role: worker\n' >> "$config"
      done
    fi
    args+=(--config "$config")
  fi

  kind "${args[@]}"
  [[ -z "$config" ]] || rm -f "$config"

  if [[ "$cni" == "calico" ]]; then
    kubectl apply -f "$manifest"
    rm -f "$manifest"
    # Nodes turn Ready before policies are enforced; wait for the calico-node pods.
    kubectl rollout status daemonset/calico-node -n kube-system --timeout=300s
  fi
  kubectl wait --for=condition=Ready nodes --all --timeout=300s
}

# Download the pinned Calico manifest and check its checksum, before any cluster exists.
fetch_calico() {
  local sum
  curl -fsSL -o "$1" \
    "https://raw.githubusercontent.com/projectcalico/calico/${CALICO_VERSION}/manifests/calico.yaml"
  sum="$(shasum -a 256 "$1" | cut -d ' ' -f 1)"
  if [[ "$sum" != "$CALICO_MANIFEST_SHA256" ]]; then
    rm -f "$1"
    echo "Calico manifest checksum mismatch: got $sum, want $CALICO_MANIFEST_SHA256" >&2
    exit 1
  fi
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
