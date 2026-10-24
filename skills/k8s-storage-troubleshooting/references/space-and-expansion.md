# Full volumes, expansion and ephemeral storage

## Investigate

How full a volume is can be seen only from inside the pod, or from the kubelet's
`kubelet_volume_stats_used_bytes` metric if the cluster's monitoring collects it.
Reading inside the container runs a program in the user's pod, so ask first:

> Ask first: the agent runs this only after the user approves it.

```bash
kubectl exec my-pod -n my-namespace -- df -h /data
```

Use the volume's real mount path. Then:

```bash
kubectl describe pvc my-data -n my-namespace
kubectl get pvc my-data -n my-namespace -o jsonpath='{.spec.resources.requests.storage}{" "}{.status.capacity.storage}{" "}{.status.conditions}{" "}{.status.allocatedResourceStatuses}{"\n"}'
kubectl get storageclass my-class -o jsonpath='{.allowVolumeExpansion}{"\n"}'
kubectl logs my-pod -n my-namespace --tail=50
```

## Read the results

- **`No space left on device`** in the app's logs, and `df` near 100%: the volume is
  full. Some provisioners do not enforce the requested size at all (kind's local-path
  ignores it), so the volume may fill the node's disk instead.
- **Expansion**: increase the claim's storage request; it works only if the class has
  `allowVolumeExpansion: true`, and a volume never shrinks. The filesystem is resized
  while the pod runs, if the filesystem supports it, or at the next pod start. A claim
  no pod uses does not finish expanding.
- **A resize in progress or stuck**: the claim's condition `Resizing`, and
  `status.allocatedResourceStatuses` with `ControllerResizeInProgress`,
  `ControllerResizeFailed`, `NodeResizePending`, `NodeResizeInProgress` or
  `NodeResizeFailed`. After a failed expansion the request may be lowered again, but not
  below the current capacity.
- **`emptyDir` and container writable layers** use the node's ephemeral storage. Going
  over a container's `ephemeral-storage` limit, or the pod's summed limits including
  `emptyDir`, gets the pod evicted; the eviction message names ephemeral storage.

## Proposed fix

Free space in the app (old files, logs), or expand the claim. Expanding cannot be
undone, since a volume never shrinks, and it may cost money on a cloud, so a human runs
it, best through the app's source (write the new size the user chooses):

> Proposed fix: review before running. The agent does not run this.

```bash
kubectl patch pvc my-data -n my-namespace --type=merge -p '{"spec": {"resources": {"requests": {"storage": "20Gi"}}}}'
# Undo: none; a volume cannot shrink back to its old size
```

If the class does not allow expansion, moving the data to a bigger new claim is a
migration for the app's owners, not a quick fix.
