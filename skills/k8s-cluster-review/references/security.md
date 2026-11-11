# Security checks

What drifted in: containers with more rights than they need, namespaces that would
accept them, broad RBAC bindings, missing NetworkPolicies and floating image tags.
Never read Secrets for any of these checks; the bindings and the pod specs say enough.

## Investigate

```bash
kubectl get deployment my-app -n my-namespace -o jsonpath='{.spec.template.spec.securityContext}{"\n"}{range .spec.template.spec.containers[*]}{.name}{" "}{.securityContext}{"\n"}{end}{.spec.template.spec.volumes}{"\n"}'
kubectl get namespace my-namespace -o jsonpath='{.metadata.labels}{"\n"}'
kubectl get clusterrolebinding my-binding -o yaml
kubectl get clusterrole my-role -o yaml
kubectl get rolebindings -n my-namespace -o custom-columns='NAME:.metadata.name,ROLE:.roleRef.name,SUBJECTS:.subjects[*].name'
kubectl get serviceaccounts -n my-namespace
kubectl get networkpolicies -n my-namespace -o yaml
kubectl get pods -n my-namespace -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.spec.containers[*].image}{" "}{.status.containerStatuses[*].imageID}{"\n"}{end}'
```

## Read the results

**securityContext.** A container field overrides the pod field of the same name; read
both. Root means neither `runAsNonRoot: true` nor a non-zero `runAsUser` is set at
either level, or `runAsUser: 0` is set. The image may still declare a non-root `USER`;
the API does not show it, so say "runs as root unless the image sets a user". Also note
`capabilities.add` with `SYS_ADMIN`, `NET_ADMIN` or `ALL`, which the baseline Pod
Security level refuses.

**Host access.** `hostNetwork`, `hostPID`, `hostIPC`, `hostPort` and `hostPath` volumes
let a pod see or change the node. Node agents need some of them: CNI and CSI drivers,
kube-proxy, log and metrics collectors (Fluent Bit, node-exporter), security agents.
Those are usually DaemonSets in an add-on namespace: name them as expected, not as
findings. A `hostPath` in an application Deployment is a finding.

**Pod Security labels.** `pod-security.kubernetes.io/enforce` is what refuses pods;
`warn` and `audit` only report. Levels: `privileged` (no limits), `baseline` (no
privileged, no host namespaces, no hostPath), `restricted` (baseline plus non-root,
`allowPrivilegeEscalation: false`, all capabilities dropped and a seccomp profile). A
namespace without the label falls back to the cluster default set in the API server's
admission configuration, which is `privileged` unless the cluster changed it; the API
does not show that default. Before proposing `enforce`, propose the server-side dry run
of the label: it lists the running pods that would violate it.

**RBAC.**

- Bindings to `cluster-admin`: in a ClusterRoleBinding the subject has full control of
  the cluster; in a RoleBinding, full control of that namespace, Secrets included.
- ClusterRoles whose rules hold `verbs: ["*"]` with `resources: ["*"]` act the same.
  Aggregated roles (`admin`, `edit`) are expected.
- Subjects starting with `system:` (`system:masters`, `system:kube-controller-manager`,
  `system:serviceaccount:kube-system:...`) belong to Kubernetes itself. Installer groups
  (kubeadm's `kubeadm:cluster-admins`, a managed cloud's cluster admin group) are fine if
  intended. A ServiceAccount of an application bound to `cluster-admin` is the usual
  real finding: anyone who can run a pod with it, or read its token, controls the
  cluster.
- For who can do what in detail, hand off to `k8s-rbac-troubleshooting`.

**NetworkPolicies.** With no policy selecting a pod, all traffic to and from it is
allowed. A namespace is covered when a policy with an empty `podSelector` denies by
default, and other policies allow what the apps need. Policies are enforced by the CNI,
not by the API server: Cilium, Calico, Antrea and kindnet on current kind releases
enforce them, Flannel alone does not, and on managed clusters it depends on the option
chosen at creation (EKS `aws-node` needs its network policy agent, AKS a policy engine).
Identify the CNI from its DaemonSet: in `kube-system`, or in its own namespace
(`calico-system`, `kube-flannel`).

A default-deny policy for one namespace, to give its owners with the allow rules they
need (DNS egress to `kube-system` is the one most often forgotten):

> Proposed fix: review before running. The agent does not run this.

```bash
kubectl create -f - <<'YAML'
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-ingress
  namespace: my-namespace
spec:
  podSelector: {}
  policyTypes: [Ingress]
YAML
# Undo: kubectl delete networkpolicy default-deny-ingress -n my-namespace
```

**Images.** `:latest`, or no tag (which means `:latest`), runs whatever the registry
held when the node last pulled; two pods of one Deployment can run different code, and
a rollback cannot return to the old image. A tag with a digest
(`my-image:1.2@sha256:...`) or a digest alone is fine. The pod's `imageID` shows the
digest that actually runs.

## Extra evidence

kube-linter (`privileged-container`, `run-as-non-root`, `privilege-escalation-container`,
`host-network`, `latest-tag`, `access-to-secrets`, `cluster-admin-role-binding`) and
Polaris (`privilegeEscalationAllowed`, `runAsRootAllowed`, `hostNetworkSet`,
`tagNotSpecified`) cover the pod checks on manifests. Scanners such as Kubescape or
Trivy, and policy engines such as Kyverno or Gatekeeper, go further; point to them, do
not reimplement them.
