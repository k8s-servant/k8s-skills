# Stuck releases: pending-install, pending-upgrade, pending-rollback

Helm records a new revision as `pending-*` when an operation starts, and as `deployed`
or `failed` when it ends. If the `helm` process dies in between (a cancelled CI job, a
killed pod running Helm, a lost terminal, an API server that went away), the revision
stays `pending-*`. Every later operation then refuses to start with
`another operation (install/upgrade/rollback) is in progress`.

## Investigate

The release status itself is only in the release Secret, so ask the user for:

> Proposed fix: review before running. The agent does not run this.

```bash
helm history my-app -n my-namespace
helm status my-app -n my-namespace
# Undo: nothing to undo, these only read (they are for the user because Helm reads its release records)
```

With kubectl, check whether something is really still running, and what was applied:

```bash
kubectl get pods -n my-namespace -o wide
kubectl rollout status deployment/my-app-podinfo -n my-namespace --timeout=10s
kubectl get pods -A | grep -i -E "helm|ci|runner"
kubectl events -n my-namespace
```

## Read the results

- **`pending-upgrade` or `pending-rollback`, and no `helm` process still running**: the
  operation was interrupted. The objects may be half updated (a rollout in progress
  from the interrupted upgrade, or finished). It does not recover by itself.
- **`pending-install`**: the first install was interrupted; there is no earlier
  revision to roll back to.
- **An operation that is really still running** (another CI job, a Flux or Argo CD
  controller using the same release): wait for it; do not touch the release.

Ask who or what runs Helm for this release, and whether a job was cancelled.

## Proposed fix

For `pending-upgrade` or `pending-rollback`, the user rolls back to the last revision
that worked (`deployed` or `superseded` in `helm history`). That records a new revision
and unlocks the release; then they run the upgrade again:

> Proposed fix: review before running. The agent does not run this.

```bash
helm rollback my-app 1 -n my-namespace --wait --timeout 5m
# Undo: helm rollback my-app <the pending revision> -n my-namespace, or run the upgrade again
```

For `pending-install` with nothing to roll back to, the user uninstalls the release and
installs it again. That deletes the objects the interrupted install created:

> Proposed fix: review before running. The agent does not run this.

```bash
helm uninstall my-app -n my-namespace --wait
# Undo: helm install my-app <chart> -n my-namespace with the same values
```

Avoid the cause: give CI jobs a timeout longer than Helm's `--timeout`, and do not
cancel them while Helm runs.
