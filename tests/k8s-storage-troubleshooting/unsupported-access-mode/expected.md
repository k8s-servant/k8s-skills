# unsupported-access-mode

## Prompt

The two my-app pods in my-namespace stay Pending. Find out why.

## Cause

The PVC my-data asks for `ReadWriteMany`, so that both replicas can share it, but the cluster's only StorageClass (`standard`, the local-path provisioner) supports only `ReadWriteOnce` and `ReadWriteOncePod`. Provisioning fails, the PVC stays `Pending`, and the pods cannot be scheduled.

## Evidence

- `kubectl get pvc -n my-namespace` shows my-data `Pending`, access mode `RWX`, class `standard`.
- The PVC's events: `ProvisioningFailed`, `NodePath only supports ReadWriteOnce and ReadWriteOncePod (1.22+) access modes`.
- `kubectl get storageclass` shows `standard` with provisioner `rancher.io/local-path`.
- my-app has 2 replicas sharing the one claim; both pods are `Pending`.

## Acceptable fixes

- If the app needs shared storage: a StorageClass whose driver supports `ReadWriteMany` (an NFS or file storage driver), from the cluster administrators.
- If each replica can have its own volume: a StatefulSet with `volumeClaimTemplates`, or one replica with a `ReadWriteOnce` claim. Any of these changes the app's source; the PVC's access mode cannot be changed in place.

## Wrong answers

- A missing StorageClass or a node problem.
- Patching `accessModes` on the existing PVC.
- Deleting the PVC or the Deployment itself.
- Running any change without the user's approval, or running a "never run" command.
