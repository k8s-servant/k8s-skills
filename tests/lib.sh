#!/usr/bin/env bash
# Shared helpers for the kind test kit. Source this file, never run it.
#
# Its main job is a safety net: scenarios break things on purpose, so every script
# must be sure it talks to the throwaway kind cluster and nothing else (for example
# the cluster a developer's default kubeconfig points at).

# Resolve the repo root from this file, so it works however the caller was invoked.
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLUSTER_NAME="k8s-skills-test"
TEST_CONTEXT="kind-${CLUSTER_NAME}"

# Always overwrite the caller's KUBECONFIG: an inherited value could point at a
# real cluster. The test cluster has its own file inside the repo (git-ignored).
CALLER_KUBECONFIG="${KUBECONFIG:-$HOME/.kube/config}"
export KUBECONFIG="$REPO_ROOT/.kube/$CLUSTER_NAME"

# Cloud scenarios (a `platform` file in the case folder) run on a real managed cluster
# instead: only the context the caller names in K8S_SKILLS_CLOUD_CONTEXT, copied into
# its own git-ignored file, and only in the scenario's own namespace.
if [[ -n "${K8S_SKILLS_CLOUD_CONTEXT:-}" ]]; then
  TEST_CONTEXT="$K8S_SKILLS_CLOUD_CONTEXT"
  export KUBECONFIG="$REPO_ROOT/.kube/cloud"
fi

# Copy the named cloud context, and nothing else, from the caller's kubeconfig.
write_cloud_kubeconfig() {
  mkdir -p "$REPO_ROOT/.kube"
  (umask 077 && KUBECONFIG="$CALLER_KUBECONFIG" kubectl config view --raw --minify \
    --flatten --context "$TEST_CONTEXT" > "$KUBECONFIG")
}

# Exit 2 unless the test cluster's kubeconfig exists and its current context is
# exactly the kind test context.
require_test_cluster() {
  local current=""
  if [[ -f "$KUBECONFIG" ]]; then
    current="$(kubectl config current-context 2>/dev/null || true)"
  fi
  if [[ "$current" != "$TEST_CONTEXT" ]]; then
    echo "refusing to run: current context is not $TEST_CONTEXT" >&2
    exit 2
  fi
}

# Thin wrapper so scenarios read as "wait_for --for=condition=Ready pod/x ...".
wait_for() {
  kubectl wait --timeout=180s "$@"
}

# Download a pinned file to $3 and fail unless its sha256 is $2. Used for every
# third-party manifest, so a changed upstream file never reaches the cluster.
fetch_verified() {
  local url="$1" want="$2" dest="$3" sum
  curl -fsSL -o "$dest" "$url"
  sum="$(shasum -a 256 "$dest" | cut -d ' ' -f 1)"
  if [[ "$sum" != "$want" ]]; then
    echo "checksum mismatch for $url: got $sum, want $want" >&2
    return 1
  fi
}
