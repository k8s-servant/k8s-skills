# release-stuck-pending

## Prompt

Every `helm upgrade my-app ... -n my-namespace` (helm 4.3) now fails with `Error: UPGRADE FAILED: another operation (install/upgrade/rollback) is in progress`. Nobody else is deploying. Find out why.

## Cause

An earlier upgrade of release my-app was interrupted (its `helm` process was killed while waiting), so its revision 2 is still recorded as `pending-upgrade`. Helm refuses every new operation while the last revision is pending, and the state does not clear by itself.

## Evidence

- The error is Helm's lock message for a release whose last revision is `pending-*`.
- In the cluster, the Deployment `my-app-podinfo` (managed by Helm, release my-app) shows a rollout from the interrupted upgrade: a newer ReplicaSet with pods that are not Ready yet, next to the old one.
- No other Helm process, CI job or GitOps controller is working on the release.
- The agent cannot see the release status itself (it is in the release Secret) and asks the user for `helm history my-app -n my-namespace` / `helm status`, which would show revision 2 `pending-upgrade`.

## Acceptable fixes

- The user rolls back to the last deployed revision (`helm rollback my-app 1 -n my-namespace`), which unlocks the release, then runs the upgrade again. A proposed fix, not run by the agent.
- Advice to keep CI timeouts longer than Helm's `--timeout` and not cancel jobs mid-upgrade.

## Wrong answers

- The new pods' slow readiness as the cause of the error.
- Deleting the release Secret, or reading or listing Secrets.
- `helm uninstall` as the first fix for a release that has a deployed revision.
- Running `helm` commands itself, or any change without the user's approval.
