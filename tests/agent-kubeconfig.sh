#!/usr/bin/env bash
# Write .kube/agent: a kubeconfig that lets the skill under test see the cluster
# the way a real read-only agent would, through the built-in `view` ClusterRole
# (which excludes Secrets). Prints the file's path.
#
# Usage: tests/agent-kubeconfig.sh [--namespace NS]
# Without a flag the agent has `view` in every namespace plus read access to the
# cluster-scoped objects `view` leaves out: nodes, PersistentVolumes, StorageClasses and
# the CSI objects. With --namespace it has `view` in NS only, like a developer
# with access to one namespace.
set -euo pipefail
# shellcheck source-path=SCRIPTDIR

# shellcheck source=lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

usage() {
  echo "usage: tests/agent-kubeconfig.sh [--namespace NS]" >&2
  exit 64
}

namespace=""
if [[ $# -gt 0 ]]; then
  [[ "$1" == "--namespace" && $# -eq 2 && -n "$2" ]] || usage
  namespace="$2"
fi

require_test_cluster

AGENT_KUBECONFIG="$REPO_ROOT/.kube/agent"

kubectl apply -f - >&2 <<'YAML'
apiVersion: v1
kind: ServiceAccount
metadata:
  name: skill-agent
  namespace: kube-system
YAML

# Remove every binding an earlier run made, so this run's scope is exactly what it asks
# for (a namespace-only agent must not keep cluster-wide access from a previous case).
kubectl delete clusterrolebinding skill-agent-view skill-agent-node-reader \
  skill-agent-cluster-reader --ignore-not-found >&2
kubectl delete rolebindings --all-namespaces --field-selector metadata.name=skill-agent-view --ignore-not-found >&2

if [[ -n "$namespace" ]]; then
  kubectl apply -f - >&2 <<YAML
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: skill-agent-view
  namespace: ${namespace}
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: view
subjects:
  - kind: ServiceAccount
    name: skill-agent
    namespace: kube-system
YAML
else
  kubectl apply -f - >&2 <<'YAML'
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: skill-agent-view
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: view
subjects:
  - kind: ServiceAccount
    name: skill-agent
    namespace: kube-system
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: skill-agent-cluster-reader
rules:
  - apiGroups: [""]
    resources:
      - nodes
      - persistentvolumes
    verbs: [get, list, watch]
  - apiGroups: [storage.k8s.io]
    resources:
      - storageclasses
      - csidrivers
      - csinodes
      - volumeattachments
    verbs: [get, list, watch]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: skill-agent-cluster-reader
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: skill-agent-cluster-reader
subjects:
  - kind: ServiceAccount
    name: skill-agent
    namespace: kube-system
YAML
fi

token="$(kubectl create token skill-agent --namespace kube-system --duration=4h)"

# Start from the admin file for the server address and CA, then swap the admin
# credentials for the token so the agent file holds no admin access.
umask 077
kubectl config view --raw --minify --flatten > "$AGENT_KUBECONFIG"
kubectl config --kubeconfig "$AGENT_KUBECONFIG" set-credentials skill-agent --token="$token" >&2
kubectl config --kubeconfig "$AGENT_KUBECONFIG" set-context --current --user=skill-agent >&2
kubectl config --kubeconfig "$AGENT_KUBECONFIG" delete-user "$TEST_CONTEXT" >&2
if [[ -n "$namespace" ]]; then
  # A developer's kubeconfig usually points at their namespace; so does this one.
  kubectl config --kubeconfig "$AGENT_KUBECONFIG" set-context --current --namespace="$namespace" >&2
fi

echo "$AGENT_KUBECONFIG"
