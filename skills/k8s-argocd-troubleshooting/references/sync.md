# Sync: never syncing, failing, or drifting back

Argo CD syncs on its own only when `spec.syncPolicy.automated` is set (and its
`enabled` field is not `false`). Otherwise an `OutOfSync` Application waits for someone
to sync it. A sync applies each rendered object; `operationState` records the result.

## Investigate

```bash
kubectl get application my-app -n argocd -o jsonpath='{.spec.syncPolicy}{"\n"}{.status.sync.status}{" "}{.status.sync.revision}{"\n"}'
kubectl get application my-app -n argocd -o jsonpath='{.status.operationState.phase}{" "}{.status.operationState.message}{"\n"}'
kubectl get application my-app -n argocd -o jsonpath='{range .status.operationState.syncResult.resources[*]}{.kind}{" "}{.name}{" "}{.status}{" "}{.message}{"\n"}{end}'
kubectl get application my-app -n argocd -o jsonpath='{range .status.history[*]}{.id}{" "}{.revision}{" "}{.deployedAt}{"\n"}{end}'
kubectl logs -n argocd statefulset/argocd-application-controller --tail=200 | grep my-app | grep -i sync
```

## Read the results

- **No `automated` in `syncPolicy`**: nothing syncs by itself; `OutOfSync` is expected.
  Argo CD logs nothing for it and sets no condition.
- **`automated` set, but no sync**: the controller logs `Skipping auto-sync: ...` with
  the reason, for example the same revision already failed (auto-sync does not retry
  a failed revision unless `retry` is set), or `Skipping sync attempt to <rev>:
  auto-sync will wipe out all resources` when the render is empty and
  `allowEmpty` is off.
- **Phase `Failed`, `one or more objects failed to apply, reason: ...`**: read
  `syncResult.resources[].message`: an invalid manifest, an immutable field
  (`field is immutable`), an admission webhook or policy that denies the object, a
  missing CRD.
- **Phase `Running` for a long time**: a sync hook (a Job with
  `argocd.argoproj.io/hook`) has not finished, or a sync wave waits for health.
- **`OutOfSync` again right after a successful sync**: the live object differs from
  Git after applying. The usual causes are a controller or webhook that changes fields
  (injected sidecars, defaults, an HPA owning `replicas`), or `status` fields. Argo CD
  ignores `status` by default since 3.0; for other fields, `ignoreDifferences` on the
  Application or a resource customization in `argocd-cm`, or server-side diff.
- **`SharedResourceWarning`** `<kind>/<name> is part of applications <a> and <b>`: two
  Applications manage the same object and keep overwriting each other.

## Proposed fix

- Sync once (ask first, see the main skill), or propose `automated` in the source.
- Fix the rejected manifest in Git, then sync or wait for auto-sync.
- Drift: add `ignoreDifferences` for the field, or stop the other writer, in the
  source.
- An immutable field: the object must be recreated. Syncing with replace or deleting it
  is a destructive change for the user:

> Proposed fix: review before running. The agent does not run this.

```bash
kubectl delete deployment my-app -n my-namespace
# Undo: the next sync recreates it from Git (automated sync, or a manual one); its pods are replaced, not kept
```
