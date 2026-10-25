# Authentication, impersonation and refusals that are not RBAC

## 401 or 403

- **401 `Unauthorized`** (kubectl: `error: You must be logged in to the server
  (Unauthorized)`): the API server did not accept the credentials at all: an expired or
  revoked token, a token for a deleted ServiceAccount or pod, a client certificate from
  another cluster, an exec plugin or OIDC login that failed. RBAC is not involved yet.
- **403 for `system:anonymous`**: the request carried no credentials. In a pod, check
  `automountServiceAccountToken` (the pod's value wins over the ServiceAccount's) and the
  `kube-api-access-*` projected volume in the pod spec. Never read the token file.
- **`connection to the server localhost:8080 was refused`** from kubectl or a client in a
  pod: it found no in-cluster credentials and fell back to the default address; the same
  automount check applies.
- **403 with `User "..." cannot ...`**: authenticated, then refused by authorization: the
  main skill and [bindings-and-roles.md](bindings-and-roles.md).

ServiceAccount tokens in pods are short-lived and rotated by the kubelet (at 80% of
their lifetime, or after 24 hours). A client that reads the token once at start gets 401
after it expires; the fix is in the client (reload the file, or use a current client
library).

## Investigate

```bash
kubectl get pod my-app-pod -n my-namespace -o jsonpath='{.spec.serviceAccountName}{" automount="}{.spec.automountServiceAccountToken}{"\n"}{range .spec.volumes[*]}{.name}{"\n"}{end}'
kubectl get serviceaccount my-app -n my-namespace -o jsonpath='{.automountServiceAccountToken}{"\n"}'
kubectl auth whoami
```

## Impersonation

Asking `auth can-i` for another subject with `--as` needs the `impersonate` verb on that kind of
subject (users, groups, or `serviceaccounts` in its namespace). Without it the answer is
a refusal about you, not about the subject, for example `cannot impersonate-on:
serviceaccount:create resource "selfsubjectaccessreviews"` (Kubernetes 1.37, with
constrained impersonation) or `cannot impersonate resource "serviceaccounts"`. Give the
command to someone allowed to impersonate.

## Refusals that are not RBAC

Admission runs after authorization, so a refusal without `User "..." cannot ...` comes
from elsewhere:

- `admission webhook "..." denied the request: ...`: a policy engine or another webhook:
  `k8s-kyverno-troubleshooting`, `k8s-gatekeeper-troubleshooting`.
- `violates PodSecurity "restricted:latest": ...`: Pod Security Admission, on pods only
  (a Deployment shows it as `FailedCreate` events of its ReplicaSet):
  `k8s-workload-troubleshooting`.
- `ValidatingAdmissionPolicy '...' with binding '...' denied request`: a built-in
  admission policy; read it with `kubectl get validatingadmissionpolicies`.

## Proposed fix

Credentials outside the cluster (kubeconfig, OIDC, cloud login) are the user's to renew.
To mount the API credentials in a pod that needs them, set
`automountServiceAccountToken: true` on the pod template, in its source:

> Proposed fix: review before running. The agent does not run this.

```bash
kubectl apply -f my-app-deployment.yaml
# Undo: kubectl apply -f my-app-deployment-before.yaml
```
