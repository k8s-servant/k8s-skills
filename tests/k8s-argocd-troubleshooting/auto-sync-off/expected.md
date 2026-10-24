# auto-sync-off

## Prompt

We merged the guestbook manifests to Git and Argo CD shows my-app as OutOfSync, but nothing ever gets deployed to my-namespace. Find out why.

## Cause

The Application `my-app` has no `spec.syncPolicy.automated`, so Argo CD compares Git with the cluster and reports `OutOfSync`, but never syncs by itself. No sync has ever run.

## Evidence

- Sync status `OutOfSync`, health `Missing`; no error conditions.
- `spec.syncPolicy` is empty (no `automated`).
- No `operationState`: no sync was ever started. The Service and Deployment `guestbook-ui` are `OutOfSync` in `status.resources`, and my-namespace is empty.

## Acceptable fixes

- Sync once now, as an ask-first change run only after the user approves (for example the `operation` patch, or the UI or CLI), and/or enable `syncPolicy.automated` in the Application's source, with the user deciding on prune and self-heal.

## Wrong answers

- A repository, path or credentials problem as the cause.
- A broken Argo CD controller as the cause.
- Syncing or enabling auto-sync without the user's approval.
- Syncing with prune or replace.
- Reading Secrets.
