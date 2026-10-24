#!/usr/bin/env bash
# Write .kube/agent: a kubeconfig that lets the skill under test see the cluster
# the way a real read-only agent would, through the built-in `view` ClusterRole
# (which excludes Secrets). Prints the file's path.
#
# Usage: tests/agent-kubeconfig.sh [--namespace NS]
# Without a flag the agent has `view` in every namespace plus read access to the
# cluster-scoped objects `view` leaves out: nodes, PersistentVolumes, StorageClasses,
# the CSI objects, admission webhook configurations and cert-manager ClusterIssuers,
# plus Argo CD's and Gatekeeper's objects, which no aggregated role covers,
# ClusterExternalSecrets, ValidatingAdmissionPolicies, Prometheus Operator, Cilium,
# Istio, Gateway API and Envoy Gateway objects, and the prometheus-operated and alertmanager-operated service proxies.
# With --namespace it has `view` in NS only, like a developer with access to one
# namespace.
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
  - apiGroups: [admissionregistration.k8s.io]
    resources:
      - validatingwebhookconfigurations
      - mutatingwebhookconfigurations
    verbs: [get, list, watch]
  # cert-manager's own view role leaves ClusterIssuers out.
  - apiGroups: [cert-manager.io]
    resources:
      - clusterissuers
    verbs: [get, list, watch]
  # Argo CD aggregates nothing to `view`.
  - apiGroups: [argoproj.io]
    resources:
      - applications
      - applicationsets
      - appprojects
    verbs: [get, list, watch]
  # Neither does Gatekeeper; its constraint kinds are generated, so take the whole group.
  - apiGroups: [templates.gatekeeper.sh]
    resources:
      - constrainttemplates
    verbs: [get, list, watch]
  - apiGroups: [constraints.gatekeeper.sh, config.gatekeeper.sh, mutations.gatekeeper.sh,
                syncset.gatekeeper.sh, status.gatekeeper.sh, expansion.gatekeeper.sh]
    resources: ["*"]
    verbs: [get, list, watch]
  # External Secrets' view role leaves ClusterExternalSecrets out.
  - apiGroups: [external-secrets.io]
    resources:
      - clusterexternalsecrets
    verbs: [get, list, watch]
  # The Prometheus Operator aggregates nothing to `view`.
  - apiGroups: [monitoring.coreos.com]
    resources: ["*"]
    verbs: [get, list, watch]
  # Prometheus' and Alertmanager's HTTP APIs (targets, rules, alerts) through the API
  # server's service proxy, on their governing Services only. RBAC cannot limit the
  # path, so the skill itself tells the agent to keep off the endpoints that return
  # the generated configuration (/api/v1/status/config, /api/v2/status).
  - apiGroups: [""]
    resources:
      - services/proxy
    # RBAC sees the proxied name with its port: "prometheus-operated:web".
    resourceNames: ["prometheus-operated", "prometheus-operated:web",
                    "alertmanager-operated", "alertmanager-operated:web"]
    verbs: [get]
  # Cilium aggregates nothing to `view` either.
  - apiGroups: [cilium.io]
    resources: ["*"]
    verbs: [get, list, watch]
  # Nor does Istio. Its own reader role also grants Secrets, so it is not used here.
  - apiGroups: [networking.istio.io, security.istio.io, telemetry.istio.io,
                extensions.istio.io]
    resources: ["*"]
    verbs: [get, list, watch]
  # The Gateway API and Envoy Gateway ship no read role at all.
  - apiGroups: [gateway.networking.k8s.io, gateway.envoyproxy.io]
    resources: ["*"]
    verbs: [get, list, watch]
  # Kubernetes' own admission policies, which Gatekeeper and Kyverno can generate.
  - apiGroups: [admissionregistration.k8s.io]
    resources:
      - validatingadmissionpolicies
      - validatingadmissionpolicybindings
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
# credentials for the token. This happens in a temp file next to the agent file, which
# is moved into place only once the admin user is gone, so .kube/agent never holds
# admin access.
umask 077
draft="$(mktemp "$AGENT_KUBECONFIG.XXXXXX")"
trap 'rm -f "$draft"' EXIT
kubectl config view --raw --minify --flatten > "$draft"
kubectl config --kubeconfig "$draft" set-credentials skill-agent --token="$token" >&2
kubectl config --kubeconfig "$draft" set-context --current --user=skill-agent >&2
kubectl config --kubeconfig "$draft" delete-user "$TEST_CONTEXT" >&2
if [[ -n "$namespace" ]]; then
  # A developer's kubeconfig usually points at their namespace; so does this one.
  kubectl config --kubeconfig "$draft" set-context --current --namespace="$namespace" >&2
fi
mv "$draft" "$AGENT_KUBECONFIG"

echo "$AGENT_KUBECONFIG"
