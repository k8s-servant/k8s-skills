# Attach and mount errors

A volume reaches a pod in two steps: it is attached to the node (for block storage,
tracked by a `VolumeAttachment`), then mounted into the pod by the kubelet and the CSI
driver's node plugin on that node. The pod stays `ContainerCreating` until both work.

kind's local-path volumes need no attach step, so this page is checked against the
docs only.

## Investigate

```bash
kubectl describe pod my-pod -n my-namespace
kubectl events -n my-namespace --for pod/my-pod
kubectl get volumeattachments
kubectl get pv my-pv -o yaml
kubectl get csidrivers
kubectl get csinode my-node -o yaml
kubectl get pods -A -o wide --field-selector spec.nodeName=my-node
```

The `VolumeAttachment` for the PV shows the node it is attached to and an
`attachError` when attaching failed. The `CSINode` object lists the drivers registered
on the node.

## Read the results

Event texts as seen on Kubernetes 1.37 (the docs do not list them):

- **`FailedAttachVolume`**: the attach step failed: the driver's controller is down, the
  cloud refused (permissions, quota, zone), or the volume is in another zone than the
  node.
- **`Multi-Attach error for volume`**: a `ReadWriteOnce` volume is still attached to
  another node, usually because the old pod there has not finished terminating (a node
  `NotReady`, a stuck pod). It clears when the old attachment is released.
- **`FailedMount`, "Unable to attach or mount volumes ... timed out waiting for the
  condition"**: the mount did not finish. The lines before it in the events usually name
  the cause: the driver not registered on the node (its node plugin pod is not running
  there), a missing ConfigMap or Secret volume source, or a filesystem error.
- **A driver missing from `CSINode`** on that node: the driver's node DaemonSet pod is
  not running there; mounts on that node fail. Check those pods.
- **A claim or PV `Terminating`**: deletion waits for the `kubernetes.io/pvc-protection`
  or `kubernetes.io/pv-protection` finalizer while a pod uses the claim or the PV is
  bound. Find the pod that still uses it.

## Proposed fix

For `Multi-Attach`, find the old pod on the other node. If that node is gone for good,
its pods and attachment are cleaned up only once the node is handled: hand over to
`k8s-node-troubleshooting`. Force-deleting the old pod can corrupt data if the node is
still writing, so a human confirms the node is off first:

> Proposed fix: review before running. The agent does not run this.

```bash
kubectl delete pod my-pod -n my-namespace --grace-period=0 --force
# Undo: none; the pod's controller creates a new one
```

Never remove a protection finalizer by hand to make a claim or PV go away: it exists so
data is not deleted while in use.
