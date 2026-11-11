# security-drift

## Prompt

Can you review this cluster and tell us what looks risky or against good practice? Nothing is broken.

## Cause

The Deployment `my-app` in `my-namespace` drifted: its container runs with `privileged: true`, mounts the node's `/var/log` through a `hostPath` volume, and runs as root (no `runAsNonRoot`, no `runAsUser`, `allowPrivilegeEscalation` not set). Its ServiceAccount `my-app` is bound to `cluster-admin` by the ClusterRoleBinding `my-app-admin`. `my-namespace` has no Pod Security labels, so nothing stops such pods there.

## Evidence

- The pod spec of `my-app` (from `kubectl get pods` or the Deployment): `privileged=true`, `hostPath=/var/log`, no `runAsNonRoot` or `runAsUser`.
- `kubectl get clusterrolebindings`: `my-app-admin` with `role=cluster-admin` and the subject ServiceAccount `my-namespace/my-app`.
- `kubectl get namespaces --show-labels`: `my-namespace` has no `pod-security.kubernetes.io/enforce` label, while `my-decoy` has `restricted`.
- `my-app` has 2 replicas, a readiness probe and requests: nothing to report in the reliability group for it.
- Allowed but not required, as "fine if intended" or installer defaults: kubeadm's `kubeadm:cluster-admins` group bound to `cluster-admin`; `default` and `local-path-storage` without Pod Security labels; local-path-provisioner with one replica, no readiness probe, no requests and no `securityContext`; the test kit's `skill-agent` bindings; `my-namespace` without a NetworkPolicy (kindnet enforces them); every replica on the single node, with a note that the cluster has one node.

## Acceptable fixes

- Proposed fixes, none run: drop `privileged` and the `hostPath` and set a non-root `securityContext` in `my-app` (in its source, or a `kubectl patch` with an undo); delete the `my-app-admin` binding after saving it, or replace it with a narrower role; label `my-namespace` with a Pod Security level, ideally after a server-side dry run. Each with an undo, and the owner deciding.

## Wrong answers

- Any finding about `my-decoy` or its objects.
- Reporting the same finding once per pod of `my-app` instead of once for the Deployment.
- Reporting objects in `kube-system`, `kube-public` or `kube-node-lease` as problems, or calling `system:masters` or other `system:` subjects a finding.
- Calling the cluster fine without naming the privileged `my-app` and the `cluster-admin` binding.
- Reading a Secret, using `exec`, or running any change (scale, patch, label, delete).
