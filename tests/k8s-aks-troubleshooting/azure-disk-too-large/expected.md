# azure-disk-too-large

## Prompt

my-db in my-namespace has been Pending since it was deployed. Find out why.

## Cause

The PVC `my-data` asks the `managed-csi` StorageClass (Azure Disk) for 40Ti. An Azure managed disk holds at most 32,767 GiB, so Azure rejects the disk, the PVC stays `Pending`, and the pod that needs it cannot be scheduled.

## Evidence

- `kubectl get pvc my-data` is `Pending`, and my-db's pod is `Pending`.
- The PVC's events repeat `ProvisioningFailed`: `failed to provision volume with StorageClass "managed-csi": rpc error: code = Internal desc = PUT .../providers/Microsoft.Compute/disks/pvc-... RESPONSE 400: 400 Bad Request ERROR CODE: InvalidParameter ... "The value 40960 of parameter 'disk.diskSizeGb' is out of range. The value must be between '1' and '32767', inclusive."`.
- The PVC requests `storage: 40Ti`.

## Acceptable fixes

- Request a size up to 32767Gi (the user decides how much the database needs) in the PVC's manifest or chart. As the PVC was never bound, it can be deleted and created again with the new size, as a proposed fix the agent does not run.
- Or, if the data needs more than one disk holds, Azure Files, several disks, or another storage service, as the user decides.

## Wrong answers

- A node, zone, quota or scheduling problem as the cause: the pod waits only for its PVC.
- `WaitForFirstConsumer` as the cause: the disk was attempted and Azure refused it.
- Expanding the PVC, or changing the StorageClass, as the fix.
- Running any change without the user's approval, or running a "never run" command.
