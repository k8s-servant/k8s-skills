#!/usr/bin/env bash
# Write .kube/agent: a kubeconfig that lets the skill under test see the cluster
# the way a real read-only agent would, through the built-in `view` ClusterRole
# (which excludes Secrets). Prints the file's path.
set -euo pipefail
# shellcheck source-path=SCRIPTDIR

# shellcheck source=lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
require_test_cluster

AGENT_KUBECONFIG="$REPO_ROOT/.kube/agent"

kubectl apply -f - >&2 <<'YAML'
apiVersion: v1
kind: ServiceAccount
metadata:
  name: skill-agent
  namespace: kube-system
---
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
YAML

token="$(kubectl create token skill-agent --namespace kube-system --duration=4h)"

# Start from the admin file for the server address and CA, then swap the admin
# credentials for the token so the agent file holds no admin access.
umask 077
kubectl config view --raw --minify --flatten > "$AGENT_KUBECONFIG"
kubectl config --kubeconfig "$AGENT_KUBECONFIG" set-credentials skill-agent --token="$token" >&2
kubectl config --kubeconfig "$AGENT_KUBECONFIG" set-context --current --user=skill-agent >&2
kubectl config --kubeconfig "$AGENT_KUBECONFIG" delete-user "$TEST_CONTEXT" >&2

echo "$AGENT_KUBECONFIG"
