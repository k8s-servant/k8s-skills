# PVC Pending, provisioning failures and Released volumes

A PVC is `Pending` until it is bound to a PersistentVolume. With a StorageClass, the
class's provisioner creates that PV. Without a matching volume or a working provisioner,
the claim stays unbound indefinitely.

## Investigate

```bash
kubectl get pvc my-data -n my-namespace -o wide
kubectl describe pvc my-data -n my-namespace
kubectl events -n my-namespace --for persistentvolumeclaim/my-data
kubectl get storageclass
kubectl get storageclass my-class -o yaml
kubectl get pv
kubectl get pods -A | grep -i -E "provisioner|csi"
```

The provisioner's own logs often explain a failure better than the event (find its pod
with the last command, then `kubectl logs` it).

## Read the results

- **`WaitForFirstConsumer` event** ("waiting for first consumer to be created before
  binding") and no failure: the class waits for a pod that uses the claim. If no pod uses
  it, Pending is expected. If a pod uses it and is Pending for another reason (CPU,
  taints, node selector), the claim waits with it: hand over to
  `k8s-node-troubleshooting`. A pod with `spec.nodeName` set bypasses the scheduler, and
  its claim stays Pending.
- **`storageclass.storage.k8s.io "my-class" not found`**: the claim names a class this
  cluster does not have, often from a manifest written for another cluster. The class
  cannot be changed on the existing claim.
- **An access mode error** (for example kind's local-path: "NodePath only supports
  ReadWriteOnce and ReadWriteOncePod"): the driver cannot provide that mode. Shared
  `ReadWriteMany` storage needs a file-storage driver.
- **`ExternalProvisioning`, "waiting for a volume to be created"** with nothing after
  it: the provisioner is not running or not working; check its pods and logs.
- **Size, parameters, quota or zone errors** in `ProvisioningFailed`: the class's
  parameters, the cloud quota, or a zone with no capacity. A `ResourceQuota` on
  `requests.storage` or `persistentvolumeclaims` in the namespace rejects the claim at
  creation instead.
- **Static PVs** (no provisioning, `storageClassName: ""`): a PV binds only if its
  class, access modes and capacity fit the claim, and its `claimRef` (if set) names it.
- **A PV `Released`**: its claim was deleted. With `persistentVolumeReclaimPolicy:
  Retain` it is not reused automatically, so the data stays for an administrator.

## Proposed fix

Fix the claim in the app's source (class, access mode, size), and let the deploy create
it. Changing the class or access mode means a new claim: see the proposed fix in
SKILL.md, for a claim that never bound only.

Making a `Released` PV available again exposes old data to a new claim, so the storage
owner decides and runs it:

> Proposed fix: review before running. The agent does not run this.

```bash
kubectl get pv my-pv -o jsonpath='{.spec.claimRef}{"\n"}'
kubectl patch pv my-pv --type=json -p '[{"op": "remove", "path": "/spec/claimRef"}]'
# Undo: put the claimRef printed by the first line back with kubectl patch pv my-pv --type=merge -p '{"spec": {"claimRef": ...}}', which works only until another claim binds the PV; after that its data is exposed to that claim
```

The documented route for a retained volume is to delete the PV, clean or keep the data
on the storage itself, and create a new PV for it.
