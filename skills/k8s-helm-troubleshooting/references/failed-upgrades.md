# Failed upgrades

An upgrade renders the chart with the new values, applies the difference, and (with
`--wait`) waits for the objects to become ready. When anything fails, the new revision
is marked `failed`, and what was already applied stays in the cluster: Helm does not
undo it unless `--rollback-on-failure` (Helm 3: `--atomic`) was set.

## Investigate

```bash
kubectl get pods -n my-namespace -o wide
kubectl get replicasets -n my-namespace -l app.kubernetes.io/managed-by=Helm
kubectl describe deployment my-app-podinfo -n my-namespace
kubectl rollout history deployment/my-app-podinfo -n my-namespace
kubectl events -n my-namespace
kubectl get jobs -n my-namespace
```

Hook Jobs (annotation `helm.sh/hook`) run before or after the upgrade; a failed one is
often deleted by its own `helm.sh/hook-delete-policy`, so look at events too.

## Read the results

| Error | Meaning |
|---|---|
| `resource <Kind>/<ns>/<name> not ready. status: InProgress, message: ...` and `context deadline exceeded` | The objects did not become ready within `--timeout`. Look at the pods: `ErrImagePull` (a tag that does not exist), `CrashLoopBackOff`, a failing readiness probe, `Pending`. Continue with `k8s-workload-troubleshooting` for the pod. |
| `pre-upgrade hooks failed: ...`, `post-upgrade hooks failed: ...` | A hook Job failed; its logs and events say why. With a pre-upgrade hook, nothing else was applied. |
| `cannot patch "<name>" with kind <Kind>: ... field is immutable` | The new chart changes a field that cannot change. The object must be recreated. |
| `"<release>" has no deployed releases` | No revision ever succeeded, so there is nothing to upgrade from or roll back to. Ask for `helm history`: if every revision is `failed` or `pending-install`, the user uninstalls the release and installs it again. |
| `current release manifest contains removed kubernetes api(s)` | The last release used an API version this cluster no longer serves; see [install-errors.md](install-errors.md). |

**The app broke after an upgrade even though Helm reported success**: compare the
current and previous ReplicaSets (`rollout history`), and ask the user for
`helm history` to see which revision changed what. With one replica and
`maxUnavailable: 1`, a rollout removes the old pod before the new one is ready, so an
image that cannot be pulled takes the app down.

## Proposed fix

- Fix the cause in the values or the chart (the image tag, the probe, the hook), then
  the user upgrades again.
- To restore service first, the user rolls back to the last good revision (see the
  main skill); the failed revision stays in the history.
- An immutable field: the user deletes the object so the next upgrade can create it
  again. This interrupts what the object serves:

> Proposed fix: review before running. The agent does not run this.

```bash
kubectl delete deployment my-app-podinfo -n my-namespace
helm upgrade my-app <chart> -n my-namespace --reuse-values --wait
# Undo: none for the delete; the upgrade recreates the Deployment from the chart, with new pods
```
