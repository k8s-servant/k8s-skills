# Rollouts that do not progress

A Deployment rollout creates a new ReplicaSet and scales it up while scaling the old one
down (by default at most 25% unavailable and 25% surge). When the new pods never become
ready, the rollout stalls. Common causes listed by the Kubernetes docs: insufficient
quota, readiness probe failures, image pull errors, insufficient permissions, limit
ranges, and application runtime misconfiguration.

The Deployment's `progressDeadlineSeconds` is how long the Deployment controller waits for
progress. Read it from the spec; 600 is only the default when the field is unset, and
`describe deployment` does not print it. After that it sets the condition `Progressing` to `False` with reason
`ProgressDeadlineExceeded`, and `kubectl rollout status` exits non-zero with
`deployment "my-app" exceeded its progress deadline`. Kubernetes takes **no other
action**: it does not roll back, and the controller keeps retrying. The condition can
also turn `False` early with reason `ReplicaSetCreateError`, and a `ReplicaFailure`
condition with reason `FailedCreate` means the ReplicaSet could not create pods at all.

## Investigate

```bash
kubectl rollout status deployment/my-app -n my-namespace --timeout=10s
kubectl describe deployment my-app -n my-namespace
kubectl get deployment my-app -n my-namespace -o jsonpath='{.status.conditions}'
kubectl get deployment my-app -n my-namespace -o jsonpath='{.spec.progressDeadlineSeconds}'
kubectl get deployment my-app -n my-namespace -o jsonpath='{.spec.selector.matchLabels}'
kubectl rollout history deployment/my-app -n my-namespace
kubectl rollout history deployment/my-app -n my-namespace --revision=2
kubectl get replicasets -n my-namespace -l app=my-app -o wide
kubectl describe replicaset my-app-5d8f7c9b6 -n my-namespace
kubectl get pods -n my-namespace -l app=my-app
```

Use the Deployment's real selector in place of `app=my-app`. Replace `my-app-5d8f7c9b6` with the name of the newest ReplicaSet (the `NewReplicaSet`
line of `describe deployment`).

## Read the results

- **Old pods `Running` and ready, new pods failing**: the rollout is stuck on the new
  revision, while the old one still serves. Find the new pods' status and open the
  matching reference: [image-pull.md](image-pull.md), [crashloop.md](crashloop.md),
  [probes.md](probes.md), [oom-and-limits.md](oom-and-limits.md),
  [pending.md](pending.md).
- **New ReplicaSet with `DESIRED` above `CURRENT`, and no new pods**: the ReplicaSet
  cannot create pods. Its events say why: quota exceeded, LimitRange violation, an
  admission webhook or policy rejection, a missing service account.
- **What changed**: `kubectl rollout history --revision=N` prints the pod template of a
  revision; compare the newest with the one before (image, environment, resources,
  probes). `CHANGE-CAUSE` is only filled when the deploy process sets the
  `kubernetes.io/change-cause` annotation.
- **Rollout paused**: `describe` shows the Deployment as paused; while paused, progress
  is not checked against the deadline and the rollout does not continue.

StatefulSets and DaemonSets have no `progressDeadlineSeconds`; they follow their own
update strategy. Run the same rollout status and history commands with
`statefulset/my-app` or `daemonset/my-app`, and read the pods' status to see where the
rollout is stuck.

## Proposed fix

Fix the cause in the new revision (image, configuration, probe, resources) through the
deployment source. As an immediate mitigation, roll back. Without options a rollback goes to
the previous revision; with `--to-revision=N` it goes to revision N.

> Proposed fix: review before running. The agent does not run this.

```bash
kubectl rollout undo deployment/my-app -n my-namespace --to-revision=1
# Undo: kubectl rollout undo deployment/my-app -n my-namespace --to-revision=2
```

A rollback through kubectl is overwritten by the next deploy from the source (and
reverted at once by a GitOps tool that syncs the Deployment), so say that the source
needs the same fix.
