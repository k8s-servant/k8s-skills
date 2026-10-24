# Memory, disk and PID pressure, and evictions

A pressure condition `True` means the kubelet crossed an eviction threshold on that
node. It adds a `NoSchedule` taint (`node.kubernetes.io/memory-pressure`,
`disk-pressure` or `pid-pressure`), reclaims what it can, and then evicts pods.

## Investigate

```bash
kubectl describe node my-node
kubectl get pods -A --field-selector spec.nodeName=my-node,status.phase=Failed
kubectl get events -A --field-selector involvedObject.kind=Node,involvedObject.name=my-node
kubectl get events -A --field-selector reason=Evicted
kubectl top node my-node
kubectl top pods -A --sort-by=memory
```

`describe pod` of an evicted pod shows `Reason: Evicted` and a message naming the
resource ("The node was low on resource: memory").

## Read the results

Default hard eviction thresholds on Linux, unless the cluster changed them:
`memory.available<100Mi`, `nodefs.available<10%`, `imagefs.available<15%`,
`nodefs.inodesFree<5%` and `imagefs.inodesFree<5%`.

- **`MemoryPressure`**: the node's free memory fell below the threshold. The kubelet
  evicts first the pods whose use exceeds their requests, then by priority, then by how
  far use exceeds requests, so pods without memory requests usually go first. One
  container killed for its own limit is an `OOMKilled`, not an eviction; that belongs to
  `k8s-workload-troubleshooting`.
- **`DiskPressure`**: the node's root filesystem, or the image filesystem, is filling up.
  Before evicting, the kubelet deletes dead pods and containers and then unused images.
  Large container logs, `emptyDir` volumes and images are the usual causes.
- **`PIDPressure`**: too many processes on the node, often one pod spawning without
  limit.
- Node-pressure eviction does not respect PodDisruptionBudgets, and evicted pods stay
  listed as `Failed` until they are cleaned up.
- Pressure that comes and goes on one node, while others are fine, usually means a pod
  on it uses far more than it requests.

## Proposed fix

Find the pod that uses the resource and fix its requests and limits (memory) or its
logs and `emptyDir` use (disk), in the source it is deployed from. Hand over to
`k8s-workload-troubleshooting` for that pod.

While you fix it, keep new pods off the node:

> Ask first: the agent runs this only after the user approves it.

```bash
kubectl cordon my-node
# Undo: kubectl uncordon my-node
```

Freeing disk on the node itself is for a human with access to it:

> Proposed fix: review before running. The agent does not run this.

```bash
df -h / /var/lib/containerd /var/lib/kubelet
sudo crictl rmi --prune
# Undo: none; pruned images are pulled again when a pod needs them
```

Changing the kubelet's thresholds or reservations is a node configuration change for
the cluster administrators, not a first fix.
